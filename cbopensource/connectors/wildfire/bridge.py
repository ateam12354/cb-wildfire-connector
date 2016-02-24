from cbint.utils.detonation import DetonationDaemon, ConfigurationError
from cbint.utils.detonation.binary_analysis import (BinaryAnalysisProvider, AnalysisPermanentError,
                                                    AnalysisTemporaryError, AnalysisResult, AnalysisInProgress)
import cbint.utils.feed
import time
import logging
import requests

from xml.etree import ElementTree


log = logging.getLogger(__name__)


class WildfireProvider(BinaryAnalysisProvider):
    def __init__(self, name, wildfire_url, wildfire_ssl_verify, api_keys):
        super(WildfireProvider, self).__init__(name)
        self.api_keys = api_keys
        self.wildfire_url = wildfire_url
        self.wildfire_ssl_verify = wildfire_ssl_verify
        self.current_api_key_index = 0
        self.session = requests.Session()

    def get_api_key(self):
        for i in range(len(self.api_keys)):
            yield self.api_keys[self.current_api_key_index]

            self.current_api_key_index += 1
            self.current_api_key_index %= len(self.api_keys)

        # if we've gotten here, we have no more keys to give.

    def query_wildfire(self, md5):
        """
        query the wildfire api to get a report on an md5
        returns a dictionary
            status_code: the wildfire api status code
            malware: 1 if determined to be malware, otherwise 0
        """
        success = False
        try:
            for apikey in self.get_api_key():
                url = self.wildfire_url + "/publicapi/get/verdict"
                payload = {'hash': md5.lower(), 'apikey': apikey}
                r = self.session.post(url, data=payload, verify=self.wildfire_ssl_verify)
                if r.status_code == 200:
                    success = True
                elif r.status_code == 404:
                    return None                # can't find the binary
                elif r.status_code == 419:
                    log.info("API query quota reached for key %s, trying next key" % apikey)
                elif r.status_code == 401:
                    log.info("API key %s unauthorized, trying next key" % apikey)
                else:
                    log.info("Received unknown HTTP status code %d from WildFire" % r.status_code)
                    log.info("-> response content: %s" % r.content)
                    raise AnalysisTemporaryError("Received unknown HTTP status code %d from WildFire" % r.status_code,
                                                 retry_in=120)

            if not success:
                raise AnalysisTemporaryError("No working WildFire API keys", retry_in=120)
        except AnalysisTemporaryError as e:
            raise
        except Exception as e:
            log.exception("Wildfire query exception: %s" % e)
            raise AnalysisTemporaryError("an exception occurred while querying wildfire: %s" % e)

        try:
            response = ElementTree.fromstring(r.content)

            # Return 0 Benign verdict
            # 1 Malware verdict
            # 2 Grayware verdict
            # -100 Verdict is pending
            # -101 Indicates a file error
            # -102 The file could not be found
            # -103 The hash submitted is invalid
            if md5.lower() == response.findtext("./get-verdict-info/md5").lower():
                verdict = response.findtext("./get-verdict-info/verdict").strip()
                if verdict == "-100":
                    return AnalysisInProgress()
                elif verdict == "-102":
                    return None                # file couldn't be found
                elif verdict.startswith("-"):
                    raise AnalysisPermanentError("WildFire could not process file: error %s" % verdict)
                elif verdict == "1":
                    return AnalysisResult(score=100)
                elif verdict == "2":
                    return AnalysisResult(score=50)
                else:
                    return AnalysisResult(score=0)
        except Exception as e:
            log.exception("Exception parsing WildFire response: %s" % e)
            raise AnalysisTemporaryError("an exception occurred while parsing wildfire response: %s" % e)

    def submit_wildfire(self, md5sum, file_stream):
        """
        submit a file to the wildfire api
        returns a wildfire submission status code
        """
        success = False
        try:
            for apikey in self.get_api_key():
                url = self.wildfire_url + "/publicapi/submit/file"
                payload = {'apikey': apikey}
                files = {'file': ('CarbonBlack_%s' % md5sum, file_stream)}
                r = self.session.post(url, data=payload, files=files, verify=self.wildfire_ssl_verify)
                if r.status_code == 200:
                    success = True
                elif r.status_code == 419:
                    log.info("API query quota reached for key %s, trying next key" % apikey)
                elif r.status_code == 401:
                    log.info("API key %s unauthorized, trying next key" % apikey)
                else:
                    log.info("Received unknown HTTP status code %d from WildFire" % r.status_code)
                    raise AnalysisTemporaryError("Received unknown HTTP status code %d from WildFire" % r.status_code,
                                                 retry_in=120)

            if not success:
                raise AnalysisTemporaryError("No working WildFire API keys", retry_in=120)
        except AnalysisTemporaryError as e:
            raise
        except Exception as e:
            import traceback
            log.error("Wildfire submission exception: %s" % e)
            log.error(traceback.format_exc())
            raise AnalysisTemporaryError("an exception occurred while submitting to wildfire: %s" % e)
        else:
            return True

    def check_result_for(self, md5sum):
        return self.query_wildfire(md5sum)

    def analyze_binary(self, md5sum, binary_file_stream):
        self.submit_wildfire(md5sum, binary_file_stream)

        retries = 20
        while retries:
            time.sleep(30)
            result = self.check_result_for(md5sum)
            if result:
                return result
            retries -= 1

        raise AnalysisTemporaryError(message="Maximum retries (20) exceeded submitting to WildFire", retry_in=120)


class WildfireConnector(DetonationDaemon):
    @property
    def filter_spec(self):
        filters = []
        max_module_len = 10 * 1024 * 1024
        filters.append('(os_type:windows) orig_mod_len:[1 TO %d]' % max_module_len)
        additional_filter_requirements = self.get_config_string("binary_filter_query", None)
        if additional_filter_requirements:
            filters.append(additional_filter_requirements)

        log.info("Filter spec is %s" % ' '.join(filters))

        return ' '.join(filters)

    @property
    def num_quick_scan_threads(self):
        return 1

    @property
    def num_deep_scan_threads(self):
        return 4

    def get_provider(self):
        wildfire_provider = WildfireProvider(self.name, self.wildfire_url, self.wildfire_ssl_verify, self.api_keys)
        return wildfire_provider

    def get_metadata(self):
        return cbint.utils.feed.generate_feed(self.name, summary="PaloAlto Wildfire cloud binary feed",
                        tech_data=("There are no requirements to share any data with Carbon Black to use this feed. "
                                   "However, binaries may be shared with Palo Alto."),
                        provider_url="http://wildfire.paloaltonetworks.com/",
                        icon_path='/usr/share/cb/integrations/wildfire/wildfire-logo.png',
                        display_name="Wildfire", category="Connectors")

    def validate_config(self):
        super(WildfireConnector, self).validate_config()

        keys = self.get_config_string("wildfire_api_keys", None)
        if not keys:
            raise ConfigurationError("WildFire API keys must be specified in the wildfire_api_keys option")
        self.api_keys = keys.split(';')

        wildfire_url = self.get_config_string("wildfire_url", "https://wildfire.paloaltonetworks.com")
        self.wildfire_url = wildfire_url.rstrip("/")

        self.wildfire_ssl_verify = self.get_config_boolean("wildfire_verify_ssl", True)

        log.info("connecting to WildFire server at %s with API keys %s" % (self.wildfire_url, self.api_keys))

        return True


if __name__ == '__main__':
    import os
    import yappi
    import logging
    logging.basicConfig(level=logging.DEBUG)

#    yappi.start()

    my_path = os.path.dirname(os.path.abspath(__file__))
    temp_directory = "/tmp/wildfire"

    config_path = os.path.join(my_path, "testing.conf")
    daemon = WildfireConnector('wildfiretest', configfile=config_path, work_directory=temp_directory,
                                    logfile=os.path.join(temp_directory, 'test.log'), debug=True)
    daemon.start()

#    yappi.get_func_stats().print_all()
#    yappi.get_thread_stats().print_all()

