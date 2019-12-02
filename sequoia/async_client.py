import logging
import platform
from sys import version_info as vi

import distro

from sequoia import __version__ as client_version
from sequoia import env, auth, http


class RegistryClient:

    def __init__(self, registry_url, owner, **config):
        import asyncio
        import os
        _auth = auth.AuthFactory.create(auth_type=auth.AuthType.NO_AUTH)
        _auth.register_adapters(config.get('adapters', None))

        self._async_executor = AsyncHttpExecutor()
        asyncio.run(
            self._async_executor.get_all(os.path.join(registry_url, 'services', owner), callback=self._get_registry))
        self._http_executor = http.HttpExecutor(auth,
                                                proxies=config.get('proxies', None),
                                                user_agent=config.get('user_aget', None),
                                                session=_auth.session,
                                                request_timeout=config.get('request_timeout', None),
                                                correlation_id=config.get('correlation_id', None),
                                                backoff_strategy=config.get('backoff_strategy', None))

    def _get_registry(self, registry_responses):
        if isinstance(registry_responses, (list, tuple)):
            self._registry_responses = registry_responses
        else:
            self._registry_responses = [registry_responses]


class AsyncClient:

    def __init__(self, registry_url,
                 owner,
                 **kwargs):
        """
        Supports next set of args:
        - `model_resolution`
        - `user_agent`
        - `request_timeout`
        - `correlation_id
        :param registry_url:
        :param proxies:
        :param user_agent:
        :param backoff_strategy:
        :param adapters:
        :param correlation_id:
        :param kwargs:
        :Keyword Arguments:
            * *extra* (``list``) --
                Extra stuff
            * *supplement* (``dict``) --
                Additional content
        """

        logging.debug('Client initialising with registry_url=`%s` and owner `%s`', registry_url, owner)
        self._owner = owner
        self._registry_url = registry_url
        self._request_timeout = kwargs.get('request_timeout', None) or env.DEFAULT_REQUEST_TIMEOUT_SECONDS

        self._proxies = kwargs.get('proxies', None)
        self._backoff_strategy = kwargs.get('backoff_strategy', None)
        self._user_agent = kwargs.get('user_agent', None)
        self._correlation_id = kwargs.get('correlation_id', None)
        self._model_resolution = kwargs.get('model_resolution', None)
        self._registry = self._initialize_registry(**kwargs)

        self._auth = auth.AuthFactory.create(token_url=self._get_token_url(),
                                             request_timeout=self._request_timeout,
                                             **kwargs)
        self._auth.register_adapters(kwargs.get('adapters', None))
        self._auth.init_session()

        self._http = http.HttpExecutor(self._auth,
                                       proxies=self._proxies,
                                       user_agent=self._user_agent,
                                       session=self._auth.session,
                                       request_timeout=self._request_timeout,
                                       correlation_id=self._correlation_id,
                                       backoff_strategy=self._backoff_strategy)

    def _initialize_registry(self, **config):
        return RegistryClient(self._registry_url, self._owner, **config)


class AsyncHttpExecutor:
    os_info = platform.platform()
    os_versions = {
        'Linux': "%s (%s)" % (distro.linux_distribution()[0], os_info),
        'Windows': "%s (%s)" % (platform.win32_ver()[0], os_info),
        'Darwin': "%s (%s)" % (platform.mac_ver()[0], os_info),
    }

    user_agent = 'sequoia-client-sdk-python/%s python/%s %s/%s' % (
        client_version,
        '%s.%s.%s' % (vi.major, vi.minor, vi.micro),
        platform.system(),
        os_versions.get(platform.system(), ''),
    )

    def __init__(self, **kwargs):
        """

        :param kwargs: supports:
            - `correlation_id`
        """
        self._config = kwargs
        self.common_headers = {
            'User-Agent': self.user_agent,
            "Content-Type": "application/vnd.piksel+json",
            "Accept": "application/vnd.piksel+json",
            "X-Correlation-ID": self._config.get('correlation_id', None)
        }

    async def get_all(self, *urls, callback=None):
        import asyncio

        if 'session' not in self.__dict__:
            await self._create_session()

        results = await asyncio.gather(*[self.get(url) for url in urls], return_exceptions=True)
        if callback:
            callback(results)
        return results

    async def get(self, url):
        if 'session' not in self.__dict__:
            await self._create_session()

        async with self.session.get(url) as resp:
            print(resp)
            return await resp.json()

    async def _create_session(self):
        import aiohttp

        self.session = await aiohttp.ClientSession().__aenter__()

    async def _close_session(self):
        import asyncio
        await self.session.__aexit__(None, None, None)
        await asyncio.sleep(0)

    DEFAULT_BACKOFF_CONF = {'interval': 0, 'max_tries': 10}

    # pylint: disable-msg=too-many-arguments
    # def __init__(self, auth, session=None, proxies=None, user_agent=None, get_delay=None, request_timeout=None,
    #              backoff_strategy=None, correlation_id=None):
    #     if user_agent is not None:
    #         self.user_agent = user_agent + self.user_agent
    #
    #     self.backoff_strategy = backoff_strategy or HttpExecutor.DEFAULT_BACKOFF_CONF
    #
    #     self.get_delay = get_delay
    #     self.session = session or Session()
    #     self.session.proxies = proxies or {}
    #     self.session.auth = auth
    #     self.correlation_id = correlation_id
    #
    #     self.request_timeout = request_timeout or env.DEFAULT_REQUEST_TIMEOUT_SECONDS
    #
    # @staticmethod
    # def create_http_error(response):
    #     try:
    #         ret = response.json()
    #     except ValueError as e:
    #         ret = "An unexpected error occurred. HTTP Status code: %s. " % response.status_code
    #         ret += "Error message: %s. " % e
    #     return error.HttpError(ret, response.status_code)
    #
    # @staticmethod
    # def return_response(response, resource_name):
    #     return HttpResponse(response, resource_name)
    #
    # def request(self, method, url, data=None, params=None, headers=None, retry_count=0, resource_name=None):
    #     import backoff
    #
    #     def fatal_code(e):
    #         return isinstance(e, error.HttpError) and \
    #                400 <= e.status_code < 500 and e.status_code != 429 \
    #                or isinstance(e, error.AuthorisationError)
    #
    #     def backoff_hdlr(details):
    #         logging.warning('Retry `%s` for args `%s` and kwargs `%s`', details['tries'], details['args'],
    #                         details['kwargs'])
    #
    #     decorated_request = backoff.on_exception(self.backoff_strategy.pop('wait_gen', backoff.constant),
    #                                              (error.ConnectionError, error.Timeout, error.TooManyRedirects,
    #                                               error.HttpError),
    #                                              giveup=fatal_code,
    #                                              on_backoff=backoff_hdlr,
    #                                              **copy.deepcopy(self.backoff_strategy))(self._request)
    #     return decorated_request(method, url, data=data,
    #                              params=params, headers=headers,
    #                              retry_count=retry_count,
    #                              resource_name=resource_name)
    #
    # def _request(self, method, url, data=None, params=None, headers=None, retry_count=0, resource_name=None):
    #     request_headers = util.merge_dicts(self.common_headers, headers)
    #     if params:
    #         params = OrderedDict(sorted(params.items()))
    #
    #     try:
    #         response = self.session.request(
    #             method, url, data=data, params=params, headers=request_headers, allow_redirects=False,
    #             timeout=self.request_timeout)
    #     except RequestException as request_exception:
    #         raise self._raise_sequoia_error(request_error=request_exception)
    #
    #     if response.is_redirect:
    #         return self.request(method, response.headers['location'], data=data, params=params, headers=request_headers,
    #                             retry_count=retry_count, resource_name=resource_name)
    #
    #     if response.status_code == 401:
    #         return self._update_token_and_retry_request(response, method, url, data=data, params=params,
    #                                                     headers=request_headers, retry_count=retry_count,
    #                                                     resource_name=resource_name)
    #
    #     if 400 <= response.status_code <= 600:
    #         self._raise_sequoia_error(response)
    #
    #     return self.return_response(response, resource_name=resource_name)
    #
    # def _update_token_and_retry_request(self, response, *request_args, **request_kwargs):
    #     try:
    #         # This can raise AuthorisationError and should not be retried
    #         self.session.auth.update_token()
    #         return self._request(*request_args, **request_kwargs)
    #     except NotImplementedError:
    #         # Auth type does not provide refresh_token
    #         self._raise_sequoia_error(response)
    #
    # def _raise_sequoia_error(self, response=None, request_error=None):
    #     if isinstance(request_error, ConnectionError):
    #         raise error.ConnectionError(str(request_error.args[0]), cause=request_error)
    #     elif isinstance(request_error, Timeout):
    #         raise error.Timeout(str(request_error.args[0]), cause=request_error)
    #     elif isinstance(request_error, TooManyRedirects):
    #         raise error.TooManyRedirects(str(request_error.args[0]), cause=request_error)
    #     else:
    #         # error with status code
    #         raise self.create_http_error(response)
    #
    # def get(self, url, params=None, resource_name=None):
    #     return self.request('GET', url, params=params, resource_name=resource_name)
    #
    # def post(self, url, data, params=None, headers=None, resource_name=None):
    #     return self.request('POST', url, data=util.wrap(data, resource_name), params=params, headers=headers,
    #                         resource_name=resource_name)
    #
    # def put(self, url, data, params=None, headers=None, resource_name=None):
    #     return self.request('PUT', url, data=util.wrap(data, resource_name), params=params, headers=headers,
    #                         resource_name=resource_name)
    #
    # def delete(self, url, params=None, resource_name=None):
    #     return self.request('DELETE', url, params=params, resource_name=resource_name)
