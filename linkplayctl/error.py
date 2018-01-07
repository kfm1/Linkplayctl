
class LinkplayException(Exception):
    pass


class APIException(LinkplayException):
    """ Error with API, such as unknown/unusual responses from device"""
    pass

class ConnectionException(LinkplayException):
    """ Error connecting to device"""
    pass