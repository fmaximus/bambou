# -*- coding: utf-8 -*-
# Copyright (c) 2011-2012 Alcatel, Alcatel-Lucent, Inc. All Rights Reserved.
#
# This source code contains confidential information which is proprietary to Alcatel.
# No part of its contents may be used, copied, disclosed or conveyed to any party
# in any manner whatsoever without prior written permission from Alcatel.
#
# Alcatel-Lucent is a trademark of Alcatel-Lucent, Inc.


import json
import logging

from copy import deepcopy

from time import time

from .exceptions import BambouHTTPError, InternalConsitencyError
from .nurest_connection import NURESTConnection, HTTP_METHOD_DELETE, HTTP_METHOD_PUT, HTTP_METHOD_POST, HTTP_METHOD_GET
from .nurest_request import NURESTRequest
from .nurest_session import _NURESTSessionCurrentContext
from .utils import NURemoteAttribute

from bambou import bambou_logger
from bambou.config import BambouConfig


class NUMetaRESTObject(type):

    @property
    def rest_name(cls):
        if cls.__name__ == "NURESTBasicUser" or cls.__name__ == "NURESTObject":
            return "Not Implemented"

        if cls.__rest_name__ is None:
            raise NotImplementedError('%s has no defined name. Implements rest_name property first.' % cls)
        return cls.__rest_name__

    @property
    def rest_resource_name(cls):
        rest_name = cls.rest_name

        if cls.is_resource_name_fixed():
            return rest_name

        last_letter = rest_name[-1]

        if last_letter == "y":

            vowels = ['a', 'e', 'i', 'o', 'u', 'y']

            if rest_name[-2].lower() not in vowels:
                rest_name = rest_name[:len(rest_name) - 1]
                rest_name += "ies"
            else:
                rest_name += "s"

        elif last_letter != "s":
            rest_name += "s"

        return rest_name


class NURESTObject(object):
    """ Determines an object as a NURESTObject one
        Provides basic saving and fetching utilities
    """

    __metaclass__ = NUMetaRESTObject
    __rest_name__ = None

    def __init__(self):
        """ Initializes the object with general information

            Args:
                creation_date: datetime when the object as been created
                external_id: external identifier of the object
                id: identifier of the object
                local_id: internal identifier of the object
                owner: string representing the owner
                parent_id: identifier of the object's parent
                parent_type: type of the parent
        """

        self._creation_date = None
        self._external_id = None
        self._id = None
        self._local_id = None
        self._owner = None
        self._parent_id = None
        self._parent_type = None
        self._parent = None
        self._last_updated_by = None
        self._last_updated_date = None
        self._is_dirty = False

        self._attributes = dict()

        self.expose_attribute(local_name=u'id', remote_name=u'ID', attribute_type=str, is_identifier=True)
        self.expose_attribute(local_name=u'parent_id', remote_name=u'parentID', attribute_type=str)
        self.expose_attribute(local_name=u'parent_type', remote_name=u'parentType', attribute_type=str)
        self.expose_attribute(local_name=u'creation_date', remote_name=u'creationDate', attribute_type=time, is_editable=False)
        self.expose_attribute(local_name=u'owner', attribute_type=str, is_readonly=True)
        self.expose_attribute(local_name=u'last_updated_date', remote_name=u'lastUpdatedDate', attribute_type=time, is_readonly=True)
        self.expose_attribute(local_name=u'last_updated_by', remote_name=u'lastUpdatedBy', attribute_type=str, is_readonly=True)

        self._fetchers_registry = dict()

    def _compute_args(self, data=dict(), **kwargs):
        """ Compute the arguments

            Try to import attributes from data.
            Otherwise compute kwargs arguments.

            Args:
                data: a dict()
                kwargs: a list of arguments
        """

        for name, remote_attribute in self._attributes.items():
            default_value = BambouConfig.get_default_attribute_value(self.__class__, name, remote_attribute.attribute_type)
            setattr(self, name, default_value)

        if len(data) > 0:
            self.from_dict(data)

        for key, value in kwargs.iteritems():
            if hasattr(self, key):
                setattr(self, key, value)

    # Properties

    @property
    def creation_date(self):
        """ Get creation date """

        return self._creation_date

    @creation_date.setter
    def creation_date(self, creation_date):
        """ Set creation date """

        self._creation_date = creation_date

    @property
    def external_id(self):
        """ Get external id """

        return self._external_id

    @external_id.setter
    def external_id(self, external_id):
        """ Set external id """

        self._external_id = external_id

    @property
    def id(self):
        """ Get object id """

        return self._id

    @id.setter
    def id(self, id):
        """ Set object id """

        self._id = id

    @property
    def local_id(self):
        """ Get local id """

        return self._local_id

    @local_id.setter
    def local_id(self, local_id):
        """ Set local id """

        self._local_id = local_id

    @property
    def owner(self):
        """ Get owner """

        return self._owner

    @owner.setter
    def owner(self, owner):
        """ Set owner """

        self._owner = owner

    @property
    def parent_id(self):
        """ Get parent id """

        return self._parent_id

    @parent_id.setter
    def parent_id(self, parent_id):
        """ Set parent id """

        self._parent_id = parent_id

    @property
    def parent_type(self):
        """ Get parent type """

        return self._parent_type

    @parent_type.setter
    def parent_type(self, parent_type):
        """ Set parent type """

        self._parent_type = parent_type

    @property
    def parent_object(self):
        """ Get parent """

        return self._parent

    @parent_object.setter
    def parent_object(self, parent):
        """ Set parent id """

        self._parent = parent

    @property
    def last_updated_by(self):
        """ Get last updated by user id info """

        return self._last_updated_by

    @last_updated_by.setter
    def last_updated_by(self, user_id):
        """ Set last updated by user id info """

        self._last_updated_by = user_id

    @property
    def last_updated_date(self):
        """ Get last updated date """

        return self._last_updated_date

    @last_updated_date.setter
    def last_updated_date(self, update_date):
        """ Set last updated by user id info """

        self._last_updated_date = update_date

    @property
    def rest_name(self):
        """ Returns the current ReST name of the object.

            Returns:
                Returns a dictionnary containing attribute information
        """
        return self.__class__.rest_name

    @property
    def rest_resource_name(self):
        """ Resource name of the object.

            It will compute the plural if needed

            Returns:
                Returns a string that represents the resouce name of the object
        """
        return self.__class__.rest_resource_name

    @property
    def fetchers(self):
        """ Return a copy of all fetchers

            Returns:
                list: list of all fetchers

            Example:
                >>> print entity.fetchers
                [<NUSubEntitiesFetcher at xxxx>, <NUOtherEntitiesFetcher at yyyy>]
        """
        return deepcopy(self._fetchers_registry.values())

    # Children

    @property
    def children_rest_names(self):
        """ Gets the list of all possible children ReST names.

            Returns:
                list: list containing all possible rest names as string

            Example:
                >>> entity = NUEntity()
                >>> entity.children_rest_names
                ["foo", "bar"]
        """

        names = []

        for fetcher in self.fetchers:
            names.append(fetcher.__class__.managed_object_rest_name())

        return names

    # Class methods

    @classmethod
    def rest_base_url(cls):
        """ Override this method to set object base url """

        controller = _NURESTSessionCurrentContext.session.login_controller
        return controller.url

    @classmethod
    def is_resource_name_fixed(cls):
        """ Boolean to say if the resource name should be fixed. Default is False """

        return False

    @classmethod
    def object_with_id(cls, id):
        """ Get a new object with the given id

            Returns:
                Returns a new instance with specified id
        """

        new_object = cls()
        new_object.id = id

        return new_object

    # URL and resource management

    def get_resource_url(self):
        """ Get resource complete url """

        name = self.__class__.rest_resource_name
        url = self.__class__.rest_base_url()

        if self.id is not None:
            return "%s/%s/%s" % (url, name, self.id)

        return "%s/%s" % (url, name)

    def get_resource_url_for_child_type(self, nurest_object_type):
        """ Get the resource url for the nurest_object type """

        return "%s/%s" % (self.get_resource_url(), nurest_object_type.rest_resource_name)

    def __str__(self):
        """ Prints a NURESTObject """

        return "%s (ID=%s)" % (self.__class__, self.id)

    def validate(self):
        """ Validate the current object attributes.

            Check all attributes and store errors

            Returns:
                Returns True if all attibutes of the object
                respect contraints. Returns False otherwise and
                store error in errors dict.

        """
        self.errors = dict()

        for local_name, attribute in self._attributes.iteritems():

            value = getattr(self, local_name, None)

            if value is None and attribute.is_required:
                self.errors[local_name] = 'Attribute %s is required' % (local_name)
                continue

            if value is None:
                continue  # without error

            if type(value) != attribute.attribute_type:
                if attribute.attribute_type != str or type(value) != unicode:
                    self.errors[local_name] = 'Attribute %s is not of type %s' % (local_name, attribute.attribute_type)
                    continue

            if attribute.min_length and len(value) < attribute.min_length:
                self.errors[local_name] = 'Attribute %s length is too short (minimum=%s)' % (local_name, attribute.min_length)
                continue

            if attribute.max_length and len(value) > attribute.max_length:
                self.errors[local_name] = 'Attribute %s length is too long (maximum=%s)' % (local_name, attribute.max_length)
                continue

            if attribute.choices and value not in attribute.choices:
                self.errors[local_name] = 'Attribute %s is not a valid option (choices=%s)' % (local_name, attribute.choices)
                continue

        return len(self.errors) == 0

    def expose_attribute(self, local_name, attribute_type, remote_name=None, display_name=None, is_required=False, is_readonly=False, max_length=None, min_length=None, is_identifier=False, choices=None, is_unique=False, is_email=False, is_login=False, is_editable=True, is_password=False, can_order=False, can_search=False):
        """ Expose local_name as remote_name

            An exposed attribute `local_name` will be sent within the HTTP request as
            a `remote_name`

        """
        if remote_name is None:
            remote_name = local_name

        if display_name is None:
            display_name = local_name

        attribute = NURemoteAttribute(local_name=local_name, remote_name=remote_name, attribute_type=attribute_type)
        attribute.display_name = display_name
        attribute.is_required = is_required
        attribute.is_readonly = is_readonly
        attribute.min_length = min_length
        attribute.max_length = max_length
        attribute.is_editable = is_editable
        attribute.is_identifier = is_identifier
        attribute.choices = choices
        attribute.is_unique = is_unique
        attribute.is_email = is_email
        attribute.is_login = is_login
        attribute.is_password = is_password
        attribute.can_order = can_order
        attribute.can_search = can_search

        self._attributes[local_name] = attribute

    def get_attributes(self):
        """ Get all attributes information

            Returns:
                Returns a dictionnary containing attribute information
        """

        return self._attributes.values()

    def get_attribute_infos(self, local_name):
        """ Get exposed attribute information

            Args:
                local_name: the attribute name

            Returns:
                A dictionary of all information

        """
        if local_name in self._attributes:
            return self._attributes[local_name]

        return None

    def is_owned_by_current_user(self):
        """ Check if the current user owns the object """

        from bambou.nurest_user import NURESTBasicUser
        current_user = NURESTBasicUser.get_default_user()
        return self._owner == current_user.id

    def parent_for_matching_rest_name(self, rest_names):
        """ Return parent that matches a rest name """

        parent = self

        while parent:
            if parent.rest_name in rest_names:
                return parent

            parent = parent.parent

        return None

    def _genealogic_types(self):
        """ Get genealogic types

            Returns:
                Returns a list of all parent types
        """

        types = []
        parent = self

        while parent:
            types.push(parent.rest_name)
            parent = parent.parent

        return types

    def _genealogic_ids(self):
        """ Get all genealogic ids

            Returns:
                 A list of all parent ids
        """

        ids = []
        parent = self

        while parent:
            ids.push(parent.id)
            parent = parent.parent

        return ids

    def _genealogy_contains_type(self, resource_name):
        """ Check if parents contains an object of type resource_name

            Args:
                resource_name: the name of the resource to find

            Returns:
                Returns True if a parent of type has been found. False otherwise.
        """

        resource_names = self._genealogic_types()
        return resource_name in resource_names

    def _genealogy_contains_id(self, id):
        """ Check if parents contains an object of type resource_name

            Args:
                id: the id of the resource to find

            Returns:
                Returns True if a parent with specific id has been found. False otherwise.
        """

        ids = self._genealogic_ids()
        return id in ids

    def get_formated_creation_date(self, format='mmm dd yyyy HH:MM:ss'):
        """ Return creation date with a given format. Default is 'mmm dd yyyy HH:MM:ss' """

        if not self._creation_date:
            return u"No date"

        return self._creation_date.strftime('mmm dd yyyy HH:MM:ss')

    # Fetchers registry

    def register_fetcher(self, fetcher, rest_name):
        """ Register a children fetcher

        """
        self._fetchers_registry[rest_name] = fetcher

    def fetcher_for_rest_name(self, rest_name):
        """ Returns the children fetcher for the given rest name

            Args:
                rest_name (string): the children rest name

            Returns:
                list: Returns the corresponding fetcher

            Example:
                >>> print entity.fetcher_for_rest_name(NUSubEntity.rest_name)
                <NUSubEntitiesFetcher at yyyy>
        """
        if rest_name not in self._fetchers_registry:
            return None

        return self._fetchers_registry[rest_name]

    # Memory management

    def discard(self):
        """ Discard the current object and its children """

        if self._is_dirty:
            return

        self._is_dirty = True
        self.will_discard()

        bambou_logger.debug("[Bambou] Discarding object %s of type %s" % (self.id, self.rest_name))

        self.discard_all_fetchers()

        self._parent = None
        self._fetchers_registry = dict()

    def will_discard(self):
        """ """
        pass

    def discard_fetcher_for_rest_name(self, rest_name):
        """ Discard children with a given rest name

            Args:
                rest_name: the rest name

        """
        bambou_logger.debug("[Bambou] %s with id %s is discarding children %s" % (self.rest_name, self._id, rest_name))
        self._fetchers_registry[rest_name] = []

    def discard_all_fetchers(self):
        """ Discard current object children """

        for rest_name in self._fetchers_registry.keys():
            self.discard_fetcher_for_rest_name(rest_name)

    # Children management

    def add_child(self, child):
        """ Add a child """

        rest_name = child.rest_name
        children = self.fetcher_for_rest_name(rest_name)

        if children is None:
            raise InternalConsitencyError('Could not find fetcher with name %s while adding %s in parent %s' % (rest_name, child, self))

        if child not in children:
            children.append(child)

    def remove_child(self, child):
        """ Remove a child """

        rest_name = child.rest_name
        children = self.fetcher_for_rest_name(rest_name)

        target_child = None

        for local_child in children:
            if local_child.id == child.id:
                target_child = local_child
                break

        if target_child:
            children.remove(target_child)

    def update_child(self, child):
        """ Update child """

        rest_name = child.rest_name
        children = self.fetcher_for_rest_name(rest_name)

        index = None

        for local_child in children:
            if local_child.id == child.id:
                index = children.index(local_child)
                break

        if index:
            children[index] = child

    # Compression / Decompression

    def to_dict(self):
        """ Converts the current object into a Dictionary using all exposed ReST attributes.

            Returns:
                dict: the dictionary containing all the exposed ReST attributes and their values.

            Example::
                >>> print entity.to_dict()
                {"name": "my entity", "description": "Hello World", "ID": "xxxx-xxx-xxxx-xxx", ...}
        """

        dictionary = dict()

        for local_name, attribute in self._attributes.iteritems():
            remote_name = attribute.remote_name

            if hasattr(self, local_name):
                value = getattr(self, local_name)

                # Removed to resolve issue http://mvjira.mv.usa.alcatel.com/browse/VSD-5940 (12/15/2014)
                # if isinstance(value, bool):
                #     value = int(value)

                if isinstance(value, NURESTObject):
                    value = value.to_dict()

                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], NURESTObject):
                    tmp = list()
                    for obj in value:
                        tmp.append(obj.to_dict())

                    value = tmp

                dictionary[remote_name] = value
            else:
                # print('Attribute %s could not be found for object %s' % (local_name, self))
                pass

        return dictionary

    def from_dict(self, dictionary):
        """ Sets all the exposed ReST attribues from the given dictionary

            Args:
                dictionary (dict): dictionnary containing the raw object attributes and their values.

            Example:
                >>> info = {"name": "my group", "private": False}
                >>> group = NUGroup()
                >>> group.from_dict(info)
                >>> print "name: %s - private: %s" % (group.name, group.private)
                "name: my group - private: False"
        """

        for remote_name, remote_value in dictionary.iteritems():
            # Check if a local attribute is exposed with the remote_name
            # if no attribute is exposed, return None
            local_name = next((name for name, attribute in self._attributes.iteritems() if attribute.remote_name == remote_name), None)

            if local_name:
                setattr(self, local_name, remote_value)
            else:
                # print('Attribute %s could not be added to object %s' % (remote_name, self))
                pass

    # HTTP Calls

    def delete(self, response_choice=1, async=False, callback=None):
        """ Delete object and call given callback in case of call.

            Args:
                response_choice (int): Automatically send a response choice when confirmation is needed
                async (bool): Boolean to make an asynchronous call. Default is False
                callback (function): Callback method that will be triggered in case of asynchronous call

            Example:
                >>> entity.delete() # will delete the enterprise from the server
        """
        return self._manage_child_object(nurest_object=self, method=HTTP_METHOD_DELETE, async=async, callback=callback, response_choice=response_choice)

    def save(self, response_choice=None, async=False, callback=None):
        """ Update object and call given callback in case of async call

            Args:
                async (bool): Boolean to make an asynchronous call. Default is False
                callback (function): Callback method that will be triggered in case of asynchronous call

            Example:
                >>> entity.name = "My Super Object"
                >>> entity.save() # will save the new name in the server
        """
        return self._manage_child_object(nurest_object=self, method=HTTP_METHOD_PUT, async=async, callback=callback, response_choice=response_choice)

    def fetch(self, async=False, callback=None):
        """ Fetch all information about the current object

            Args:
                async (bool): Boolean to make an asynchronous call. Default is False
                callback (function): Callback method that will be triggered in case of asynchronous call

            Returns:
                tuple: (current_fetcher, callee_parent, fetched_bjects, connection)

            Example:
                >>> entity = NUEntity(id="xxx-xxx-xxx-xxx")
                >>> entity.fetch() # will get the entity with id "xxx-xxx-xxx-xxx"
                >>> print entity.name
                "My Entity"
        """

        if self.id is None:
            raise InternalConsitencyError("Cannot fetch an object that does not have an ID")

        request = NURESTRequest(method=HTTP_METHOD_GET, url=self.get_resource_url())

        if async:
            return self.send_request(request=request, async=async, local_callback=self._did_retrieve, remote_callback=callback)
        else:
            connection = self.send_request(request=request)
            return self._did_retrieve(connection)

    # REST HTTP Calls

    def send_request(self, request, async=False, local_callback=None, remote_callback=None, user_info=None):
        """ Sends a request, calls the local callback, then the remote callback in case of async call

            Args:
                request: The request to send
                local_callback: local method that will be triggered in case of async call
                remote_callback: remote moethd that will be triggered in case of async call
                user_info: contains additionnal information to carry during the request

            Returns:
                Returns the object and connection (object, connection)
        """

        callbacks = dict()

        if local_callback:
            callbacks['local'] = local_callback

        if remote_callback:
            callbacks['remote'] = remote_callback

        connection = NURESTConnection(request=request, async=async, callback=self._did_receive_response, callbacks=callbacks)
        connection.user_info = user_info

        bambou_logger.info('Bambou Sending >>>>>>\n%s %s with following data:\n%s' % (request.method, request.url, json.dumps(request.data, indent=4)))

        return connection.start()

    def _manage_child_object(self, nurest_object, method=HTTP_METHOD_GET, async=False, callback=None, handler=None, response_choice=None, commit=False):
        """ Low level child management. Send given HTTP method with given nurest_object to given ressource of current object

            Args:
                nurest_object: the NURESTObject object to manage
                method: the HTTP method to use (GET, POST, PUT, DELETE)
                callback: the callback to call at the end
                handler: a custom handler to call when complete, before calling the callback
                commit: True to auto commit changes in the current object

            Returns:
                Returns the object and connection (object, connection)
        """
        url = None

        if method == HTTP_METHOD_POST:
            url = self.get_resource_url_for_child_type(nurest_object.__class__)
        else:
            url = self.get_resource_url()

        if response_choice is not None:
            url += '?responseChoice=%s' % response_choice

        request = NURESTRequest(method=method, url=url, data=nurest_object.to_dict())
        user_info = {'nurest_object': nurest_object, 'commit': commit}

        if not handler:
            handler = self._did_perform_standard_operation

        if async:

            return self.send_request(request=request, async=async, local_callback=handler, remote_callback=callback, user_info=user_info)
        else:
            connection = self.send_request(request=request, user_info=user_info)
            return handler(connection)


    # REST Operation handlers

    def _did_receive_response(self, connection):
        """ Receive a response from the connection """

        if connection.has_timeouted:
            bambou_logger.info("NURESTConnection has timeout.")
            return

        has_callbacks = connection.has_callbacks()
        should_post = not has_callbacks

        response_code = connection._response.status_code
        log_message = 'Bambou <<<<< Response [%s] for\n%s %s\n%s' % (response_code, connection._request.method, connection._request.url, json.dumps(connection._response.data, indent=4))
        level = logging.INFO

        if response_code >= 300:
            level = logging.WARNING

        bambou_logger.log(level, log_message)

        if  connection.handle_response_for_connection(should_post=should_post) and has_callbacks:
            callback = connection.callbacks['local']
            callback(connection)

    def _did_retrieve(self, connection):
        """ Callback called after fetching the object """

        response = connection.response

        try:
            self.from_dict(response.data[0])
        except:
            pass

        return self._did_perform_standard_operation(connection)

    def _did_perform_standard_operation(self, connection):
        """ Performs standard opertions """

        if connection.async:
            callback = connection.callbacks['remote']

            if connection.user_info and 'nurest_object' in connection.user_info:
                callback(connection.user_info['nurest_object'], connection)
            else:
                callback(self, connection)
        else:
            if connection.response.status_code >= 400 and BambouConfig._should_raise_bambou_http_error:
                raise BambouHTTPError(connection=connection)

            # Case with multiple objects like assignment
            if connection.user_info and 'nurest_objects' in connection.user_info:

                if connection.user_info['commit']:
                    for nurest_object in connection.user_info['nurest_objects']:
                        self.add_child(nurest_object)
                return (connection.user_info['nurest_objects'], connection)

            if connection.user_info and 'nurest_object' in connection.user_info:

                if connection.user_info['commit']:
                    self.add_child(connection.user_info['nurest_object'])

                return (connection.user_info['nurest_object'], connection)

            return (self, connection)

    # Advanced REST Operations

    def create_child(self, nurest_object, response_choice=None, async=False, callback=None, commit=True):
        """ Add given nurest_object to the current object

            For example, to add a child into a parent, you can call
            parent.create_child(nurest_object=child)

            Args:
                nurest_object (bambou.NURESTObject): the NURESTObject object to add
                response_choice (int): Automatically send a response choice when confirmation is needed
                async (bool): should the request be done asynchronously or not
                callback (function): callback containing the object and the connection

            Returns:
                Returns the object and connection (object, connection)

            Example:
                >>> entity = NUEntity(name="Super Entity")
                >>> parent_entity.create_child(entity) # the new entity as been created in the parent_entity
        """

        # if nurest_object.id:
        #     raise InternalConsitencyError("Cannot create a child that already has an ID: %s." % nurest_object)

        return self._manage_child_object(nurest_object=nurest_object,
                                         async=async,
                                         method=HTTP_METHOD_POST,
                                         callback=callback,
                                         handler=self._did_create_child,
                                         response_choice=response_choice,
                                         commit=commit)

    def instantiate_child(self, nurest_object, from_template, response_choice=None, async=False, callback=None, commit=True):
        """ Instantiate an nurest_object from a template object

            Args:
                nurest_object: the NURESTObject object to add
                from_template: the NURESTObject template object
                callback: callback containing the object and the connection

            Returns:
                Returns the object and connection (object, connection)

            Example:
                >>> parent_entity = NUParentEntity(id="xxxx-xxxx-xxx-xxxx") # create a NUParentEntity with an existing ID (or retrieve one)
                >>> other_entity_template = NUOtherEntityTemplate(id="yyyy-yyyy-yyyy-yyyy") # create a NUOtherEntityTemplate with an existing ID (or retrieve one)
                >>> other_entity_instance = NUOtherEntityInstance(name="my new instance") # create a new NUOtherEntityInstance to be intantiated from other_entity_template
                >>>
                >>> parent_entity.instantiate_child(other_entity_instance, other_entity_template) # instatiate the new domain in the server
        """

        # if nurest_object.id:
        #     raise InternalConsitencyError("Cannot instantiate a child that already has an ID: %s." % nurest_object)

        if not from_template.id:
            raise InternalConsitencyError("Cannot instantiate a child from a template with no ID: %s." % from_template)

        nurest_object.template_id = from_template.id
        return self._manage_child_object(nurest_object=nurest_object,
                                         async=async,
                                         method=HTTP_METHOD_POST,
                                         callback=callback,
                                         handler=self._did_create_child,
                                         response_choice=response_choice,
                                         commit=commit)

    def _did_create_child(self, connection):
        """ Callback called after adding a new child nurest_object """

        response = connection.response
        try:
            connection.user_info['nurest_object'].from_dict(response.data[0])
        except Exception:
            pass

        return self._did_perform_standard_operation(connection)

    def assign(self, objects, nurest_object_type, async=False, callback=None, commit=True):
        """ Reference a list of objects into the current resource

            Args:
                objects (list): list of NURESTObject to link
                nurest_object_type (type): Type of the object to link
                callback (function): Callback method that should be fired at the end

            Returns:
                Returns the current object and the connection (object, connection)

            Example:
                >>> entity.assign([entity1, entity2, entity3], NUEntity) # entity1, entity2 and entity3 are now part of the entity
        """

        ids = list()

        for nurest_object in objects:
            ids.append(nurest_object.id)

        url = self.get_resource_url_for_child_type(nurest_object_type)
        request = NURESTRequest(method=HTTP_METHOD_PUT, url=url, data=ids)
        user_info = {'nurest_objects': objects, 'commit': commit}

        if async:
            return self.send_request(request=request,
                              async=async,
                              local_callback=self._did_perform_standard_operation,
                              remote_callback=callback,
                              user_info=user_info)
        else:
            connection = self.send_request(request=request,
                                           user_info=user_info)

            return self._did_perform_standard_operation(connection)

    # Comparison

    def rest_equals(self, rest_object):
        """ Compare objects REST attributes

        """
        if not self.equals(rest_object):
            return False

        return self.to_dict() == rest_object.to_dict()

    def equals(self, rest_object):
        """ Compare with another object """

        if self._is_dirty:
            return False

        if rest_object is None:
            return False

        if not isinstance(rest_object, NURESTObject):
            raise TypeError('The object is not a NURESTObject %s' % rest_object)

        if self.rest_name != rest_object.rest_name:
            return False

        if self.id and rest_object.id:
            return self.id == rest_object.id

        if self.local_id and rest_object.local_id:
            return self.local_id == rest_object.local_id

        return False
