# -*- coding: utf-8 -*-

import uuid

from restnuage.nurest_user import NURESTBasicUser
from restnuage.nurest_request import NURESTRequest


class RESTFetcher(object):
    """ Object fetcher for childrens """

    def __init__(self):
        """ Initliazes the fetcher """

        self._remote_name = self.__class__.managed_class.get_resource_name()
        self._nurest_object = None
        self._local_name = None
        self._master_filter = False
        self._master_order_by = None
        self._transaction_id = None
        self._last_connnection = None
        self._total_count = 0
        self._page_size = 0
        self._latest_loaded_page = 0
        self._ordered_by = ''

    # Properties

    def _get_object(self):
        """ Get object to fetch """
        return self._nurest_object

    def _set_object(self, nurest_object):
        """ Set object to fetch """
        self._nurest_object = nurest_object

    nurest_object = property(_get_object, _set_object)

    def _get_local_name(self):
        """ Get local name to fetch """
        return self._local_name

    def _set_local_name(self, local_name):
        """ Set local name to fetch """
        self._local_name = local_name

    local_name = property(_get_local_name, _set_local_name)

    # Methods

    @classmethod
    def managed_class(cls):
        """ Returns the type of the object that is managed within this fetcher """

        raise NotImplementedError('%s has no managed class. Implements managed_class method first.' % cls)

    @classmethod
    def fetcher_with_entity(cls, nurest_object, local_name):
        """ Fetch an attribute of the object """

        fetcher = RESTFetcher()
        fetcher.nurest_object = nurest_object
        fetcher.local_name = local_name

        #setattr(nurest_object, local_name, [])
        #nurest_object.register_children(getattr(nurest_object, local_name), cls.managed_class.get_resource_name())

        return fetcher

    def flush(self):
        """ Removes all objects  """
        setattr(self.nurest_object, self.local_name, [])

    def new(self):
        """ Instanciates a new instance of managed class """

        managed_class = self.managed_class()
        return managed_class()

    def _prepare_headers(self, request, filter=None, page=None):
        """ Prepare headers for the given request """

        if self._master_filter:
            request.set_header('X-Nuage-Filter', self._master_filter)
        elif filter:  # TODO: Cappuccino master filter is a CPPredicate
            request.set_header('X-Nuage-Filter', filter)

        if self._master_order_by:
            request.set_header('X-Nuage-OrderBy', self._master_order_by)

        if page:
            request.set_header('X-Nuage-Page', page)

        if self._group_by:
            header = ""

            for index, group in enumerate(self._group_by):
                header += group

                if index + 1 < len(self._group_by):
                    header += ", "

            request.set_header('X-Nuage-GroupBy', 'true')
            request.set_header('X-Nuage-Attributes', header)

    def fetch_entities(self, callback=None):
        """ Fetch entities and call the callback method """

        return self.fetch_matching_entities(callback=callback)

    def fetch_matching_entities(self, filter=None, page=None, callback=None):
        """ Fetch entities that matches filter and page"""

        request = None

        if isinstance(self._nurest_object, NURESTBasicUser):
            request = NURESTRequest(method="GET", url=self._remote_name)
        else:
            url = self._nurest_object.get_resource_url() + self._remote_name
            request = NURESTRequest(method="GET", url=url)

        self._prepare_headers(request=request, filter=filter, page=page)
        self._transaction_id = uuid.uuid4().hex

        self._nurest_object.send_request(request=request, local_callback=self._did_fetch_entities, remote_callback=callback)

        return self._transaction_id

    def _did_fetch_entities(self, result, connection):
        """ Fetching entities has been done """

        self._last_connnection = connection
        response = connection.response

        if response.status_code != 200:
            self._total_count = 0
            self._page_size = 0
            self._latest_loaded_page = 0
            self._ordered_by = ''
            self._send_content(objects=None, connection=connection)
            return

        results = response.data
        destination = getattr(self.nurest_object, self._local_name)
        fetched_objects = list()

        self._total_count = int(response.headers['X-Nuage-Count'])
        self._page_size = int(response.headers['X-Nuage-PageSize'])
        self._latest_loaded_page = int(response.headers['X-Nuage-Page'])
        self._ordered_by = response.headers['X-Nuage-OrderBy']

        for result in results:

            nurest_object = self.new()
            nurest_object.from_dict(result)
            nurest_object.parent = self._nurest_object

            if nurest_object not in destination:
                destination.append(nurest_object)

            fetched_objects.append(nurest_object)

        self._send_content(objects=fetched_objects, connection=connection)

    def count(self, callback=None):
        """ Retrieve count of entities and call callback method  """

        self.count_matching(callback=callback)

    def count_matching(self, filter=None, callback=None):
        """ Retrieve count of entities that matches filter and call callback method """

        request = None

        if isinstance(self._nurest_object, NURESTBasicUser):
            request = NURESTRequest(method="HEAD", url=self._remote_name)
        else:
            url = url = self.get_resource_url() + self._remote_name
            request = NURESTRequest(method="HEAD", url=url)

        self._prepare_headers(request=request, filter=filter, page=None)

        self._nurest_object.send_request(request=request, local_callback=self._did_count, remote_callback=callback)

    def _did_count(self, result, connection):
        """ Called when count if finished """

        response = connection.response
        count = int(response.headers['X-Nuage-Count'])
        callback = connection.callbacks['remote']

        if callback:
            callback(self, self._nurest_object, count)

    def _send_content(self, content, connection):
        """ Send a content array from the connection """

        if connection:

            callback = connection.callbacks['remote']

            if callback:
                callback(self, self._nurest_object, content)

    def latests_sort_descriptors(self):
        """ Returns an array of descriptors """

        raise NotImplementedError('Check CPSortDescriptor before implementation')
