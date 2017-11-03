import base64
import json
import sys
import os
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer
from twisted.internet import reactor, defer
from twisted.web.client import Agent
# here,we use oauth2client==4.1.2
from oauth2client.service_account import ServiceAccountCredentials

SERVICE_ADDRESS = "https://speech.googleapis.com/v1/speech:recognize"
"""The default address of the service."""

# sample rate of audio
SAMPLE_RATE = 8000

ENCODING = "LINEAR16"

LANGUAGE_CODE = "en-US"

SERVICE_ACCOUNT_FILE_PATH = '<filepath of service account>'


@implementer(IBodyProducer)
class StringProducer(object):
    # implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class SpeechResponseReceived(Protocol):
    """
    It used for convert agent received speech response into proper format.
    """
    def __init__(self, finished):
        self.finished = finished
        self.remaining = 1024 * 10

    def dataReceived(self, bytes):
        if self.remaining:
            display = bytes[:self.remaining]
            try:
                a = json.loads(display.decode("utf-8"))
                print('Speech response : %s' % a)
            except Exception as e:
                print('Error during speech response received : %s ' % e)
            reactor.stop()
            self.remaining -= len(display)

    def connectionLost(self, reason):
        self.finished.callback(None)


class RestSpeechAPI:
    """
    It is provide method to call twisted agent method to request google speech rest api.
    """

    def __init__(self):
        self.payload = None
        self.service_account_object = None

    def start_process(self, data=None):
        """
        It is fetch details from service account file for access token.
        It will be use later in speech rest api.
        :param data: file path.
        :return: defer callback.
        """
        global SERVICE_ACCOUNT_FILE_PATH
        self.service_account_object = ServiceAccountCredentials.from_json_keyfile_name(
                                                        filename=SERVICE_ACCOUNT_FILE_PATH,
                                                        scopes='https://www.googleapis.com/auth/cloud-platform')
        self.service_account_object.get_access_token()
        df = self.convert_audio(data=data)
        df.addCallback(self.call_api)
        df.addErrback(self.errCallback)
        return df

    def errCallback(self, args=None):
        """
        Error callback
        :param args: defer argument.
        :return: defer callback.
        """
        return args

    def call_api(self, args=None):
        """
        It request google speech rest api using twisted agent.
        :param args: defer argument.
        :return: defer callback.
        """
        agent = Agent(reactor)
        d = agent.request(
            str.encode('POST'),
            # 'GET',
            str.encode(SERVICE_ADDRESS),
            Headers(
                {
                    'Content-Type': ['application/json', ],
                    'Authorization': ['Bearer %s' % str(self.service_account_object.access_token), ],
                }
            ),
            StringProducer(self.payload)
        )
        return d

    def convert_audio(self, args=None, data=None):
        """
        It convert audio to base64 encoding and create payload for google speech rest api.
        :param args: defer argument.
        :param data: file path
        :return: defer callback.
        """
        # encoding audio file with Base64 (~200KB, 15 secs)
        try:
            with open(data, 'rb') as speech:
                speech_content = base64.b64encode(speech.read())

            # Try with curl command to get response using access token
            curl_config = {
                "config": {
                    "encoding": ENCODING,
                    "sampleRateHertz": SAMPLE_RATE,
                    "languageCode": LANGUAGE_CODE,
                    "enableWordTimeOffsets": False,
                },
                "audio": {
                    "content": speech_content.decode('UTF-8'),
                },
            }
            # new_json = json.dumps(curl_config)
            self.payload = str.encode(json.dumps(curl_config))
            # print('payload complete.')
            return defer.succeed('payload complete')
        except Exception as e:
            print('error during payload creation : %s' % e)
            return defer.fail({'msg': 'fail during payload creation'})


def success_callback(args=None):
    """
    It is used for convert agent response into proper format.
    :param args: defer argument.
    :return: defer callback
    """
    print('Success callback : %s' % args)
    finished = Deferred()
    args.deliverBody(SpeechResponseReceived(finished))
    return args


def error_callback(args=None):
    """
    It is error callback.
    :param args: defer argument.
    :return: defer callback.
    """
    print('Error in callback : %s' % args)
    return args


def main(data):
    """
    It call restspeechapi class and send file path to it's method.
    :param data: file path
    :return: None
    """
    speech = RestSpeechAPI()
    df = speech.start_process(data=data)
    df.addCallback(success_callback)
    df.addErrback(error_callback)
    # df.addBoth(reactor.stop)


if __name__ == '__main__':
    if os.path.isfile(sys.argv[1]):
        print('File Exists : %s' % sys.argv[1])
        main(sys.argv[1])
    else:
        print('File Not available.')
        reactor.callLater(1, reactor.stop)

reactor.run()
