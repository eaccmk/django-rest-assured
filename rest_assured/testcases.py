from django.db.models import Manager
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase


class BaseRESTAPITestCase(APITestCase):

    """Base test case class for testing REST API endpoints."""

    #: *required*: Base route name of the API endpoints to test.
    base_name = None
    #: *required*: The factory class to use for creating the main object to test against.
    factory_class = None
    #: Suffix for list endpoint view names. Defaults to ``'-list'``.
    LIST_SUFFIX = '-list'
    #: Suffix for detail endpoint view names. Defaults to ``'-detail'``.
    DETAIL_SUFFIX = '-detail'
    #: The field to use for DB and route lookups. Defaults to ``'pk'``.
    lookup_field = 'pk'
    #: User factory to use in case you need to login for auth/permissions testing. Defaults to ``None``.
    user_factory = None
    #: Whether to use token authentication instead of session. Defaults to ``False``.
    use_token_auth = False
    #: The main test subject.
    object = None
    #: The user instance created if the ``user_factory`` is set and used. Defaults to ``False``.
    user = None

    def get_factory_class(self):
        """Return the factory class for generating the main object (or model instance) of this test case.

        By default this gets the ``factory_class`` attribute of this class.

        :returns: Factory class used for creating the mock objects.
        """

        return getattr(self, 'factory_class')

    def get_object(self, factory):
        """Create and return the object (or model instance) of this test case.

        By default this calls the ``create()`` method of the factory class, assuming
        a Django Model or a factory_boy's Factory.

        :param factory: The factory class used for creating
        :returns: The main object of this test case.
        """

        return factory.create()

    def get_credentials(self, user):
        """Return the credentials dictionary.

        By default this consists getting the ``username`` field of the ``user`` instance
        and the ``raw_password`` attribute of the ``user_factory`` attribute of this class.

        :param user: The user instance that will be used to login.
        :returns: A dictionary of credentials for user login.

        .. admonition:: example

            .. code:: python

                {'username': 'ydaniv'
                 'password': 'bellbottoms'}

        .. note: This method assumes you set the user's password in plain text in ``user_factory.raw_password``.
        """

        return {
            'username': user.get_username(),
            'password': self.user_factory.raw_password}

    def setUp(self):
        """Generates the main object and user instance if needed.

        | The user will also be logged in automatically, using the ``login()`` method of the test's client.
        | You can opt for token authentication by setting the class' ``use_token_auth`` to ``True``.

        The user instance will be created only if the ``user_factory`` attribute is set to the factory class.
        """

        # create a user and log in to get permissions
        user_factory = getattr(self, 'user_factory')
        if user_factory:
            self.user = user_factory.create()
            if self.use_token_auth:
                token = Token.objects.get(user=self.user)
                self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
            else:
                self.client.login(**self.get_credentials(self.user))

        # create the object
        self.object = self.get_object(self.get_factory_class())


class ListAPITestCaseMixin(object):

    """Adds a list view test to the test case."""

    def test_list(self, **kwargs):
        """Send request to the list view endpoint, verify and return the response.

        Checks for a 200 status code and that there is a ``results`` property in the ``response.data``.

        You can extend it for more extensive checks.

        .. admonition:: example

            .. code:: python

                class LanguageRESTAPITestCase(ListAPITestCaseMixin, BaseRESTAPITestCase):

                    def test_list(self, **kwargs):
                        response = super(LanguageRESTAPITestCase, self).test_list(**kwargs)
                        results = response.data.get('results')
                        self.assertEqual(results[0].get('code'), self.object.code)

        :param kwargs: Extra arguments that are passed to the client's ``get()`` call.
        :returns: The view's response.
        """

        listview = reverse(self.base_name + self.LIST_SUFFIX)
        response = self.client.get(listview, **kwargs)

        if response.status_code != status.HTTP_200_OK:
            print '\n%s' % response.data

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

        return response


class DetailAPITestCaseMixin(object):

    """Adds a detail view test to the test case."""

    #:| A list of attribute names to check equality between the main object and the response data.
    #:| Defaults to ``['id']``.
    #:| You can also use a tuple of a string and a callable, that takes the object and returns an attribute's value.
    attributes_to_check = ['id']

    def test_detail(self, **kwargs):
        """Send request to the detail view endpoint, verify and return the response.

        Checks for a 200 status code and that there is an ``id`` property in the ``response.data``
        and that it equals the main object's id.

        You can extend it for more extensive checks.

        .. admonition:: example

            .. code:: python

                class LanguageRESTAPITestCase(DetailAPITestCaseMixin, BaseRESTAPITestCase):

                    def test_list(self, **kwargs):
                        response = super(LanguageRESTAPITestCase, self).test_list(**kwargs)
                        self.assertEqual(response.data.get('code'), self.object.code)

        Using a callable in ``attributes_to_check``:

        .. admonition:: example

            .. code:: python

                class TaggedFoodRESTAPITestCase(DetailAPITestCaseMixin, BaseRESTAPITestCase):

                    attributes_to_check = ['name', ('similar', lambda obj: obj.tags.similar_objects())]


        :param kwargs: Extra arguments that are passed to the client's ``get()`` call.
        :returns: The view's response.
        """

        object_id = getattr(self.object, self.lookup_field)

        detailview = reverse(self.base_name + self.DETAIL_SUFFIX, args=[unicode(object_id)])
        response = self.client.get(detailview, **kwargs)

        if response.status_code != status.HTTP_200_OK:
            print '\n%s' % response.data

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._check_attributes(response.data)

        return response

    def _check_attributes(self, data):
        for attr in self.attributes_to_check:
            if isinstance(attr, (tuple, list, set)):
                value = attr[1](self.object)
                attr = attr[0]
            else:
                value = unicode(getattr(self.object, attr))

            self.assertEqual(value, data[attr])


class CreateAPITestCaseMixin(object):

    """Adds a create view test to the test case."""

    #: *required*: Dictionary of data to use as the POST request's body.
    create_data = None

    def get_create_data(self):
        """Return the data used for the create request.

        By default gets the ``create_data`` attribute of this class.

        :returns: The data dictionary.
        """

        return getattr(self, 'create_data')

    def test_create(self, data=None, **kwargs):
        """Send request to the create view endpoint, verify and return the response.

        Also verifies that the object actually exists in the database.

        :param data: A dictionary of the data to use for the create request.
        :param kwargs: Extra arguments that are passed to the client's ``post()`` call.
        :returns: The view's response.
        """

        if data is None:
            data = self.get_create_data()

        create_view = reverse(self._get_create_name())
        response = self.client.post(create_view, data or {}, **kwargs)

        if response.status_code != status.HTTP_201_CREATED:
            print '\n%s' % response.data

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # another sanity check:
        # getting the instance from database simply to see that it's found and does not raise any exception
        created = self.object.__class__.objects.get(id=response.data.get('id'))

        return response, created

    def _get_create_name(self):
        if hasattr(self, 'create_name'):
            view_name = self.create_name
        else:
            view_name = self.base_name + self.LIST_SUFFIX

        return view_name


class DestroyAPITestCaseMixin(object):

    """Adds a destroy view test to the test case."""

    def test_destroy(self, **kwargs):
        """Send request to the destroy view endpoint, verify and return the response.

        Also verifies the object does not exist anymore in the database.

        :param kwargs: Extra arguments that are passed to the client's ``delete()`` call.
        :returns: The view's response.
        """

        object_id = getattr(self.object, self.lookup_field)

        destroyview = reverse(self._get_destroy_name(),
                              args=(object_id,))
        response = self.client.delete(destroyview, **kwargs)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Another sanity check:
        # see that the instance is removed from the database.
        self.assertRaises(ObjectDoesNotExist, self.object.__class__.objects.get, **{self.lookup_field: object_id})

        return response

    def _get_destroy_name(self):
        if hasattr(self, 'destroy_name'):
            view_name = self.destroy_name
        else:
            view_name = self.base_name + self.DETAIL_SUFFIX

        return view_name


class UpdateAPITestCaseMixin(object):

    """Adds an update view test to the test case."""

    #: Whether to send a PATCH request instead of PUT. Defaults to ``True``.
    use_patch = True
    #: *required*: Dictionary of data to use as the update request's body.
    update_data = None
    #:| Dictionary mapping attributes to values to check against the updated instance in the database.
    #:| Defaults to ``update_data``.
    update_results = None

    def get_update_data(self):
        """Return the data used for the update request.

        By default gets the ``update_data`` attribute of this class.

        :returns: Data dictionary for the update request.
        """

        return getattr(self, 'update_data')

    def get_update_results(self, data=None):
        """Return a dictionary of the expected results of the instance.

        By default gets the ``update_results`` attribute of this class.
        If that isn't set defaults to the data.

        :param data: The update request's data dictionary.
        :returns: Dictionary mapping instance properties to expected values.
        """

        return getattr(self, 'update_results', data)

    def test_update(self, data=None, results=None, use_patch=None, **kwargs):
        """Send request to the update view endpoint, verify and return the response.

        :param data: Data dictionary for the update request.
        :param results: Dictionary mapping instance properties to expected values.
        :param kwargs: Extra arguments that are passed to the client's ``put()`` or ``patch()`` call.
        :returns: The view's response.
        """

        object_id = getattr(self.object, self.lookup_field)
        update_view = reverse(self._get_update_name(),
                              args=(object_id,))
        if data is None:
            data = self.get_update_data()

        if results is None:
            results = self.get_update_results(data)

        args = [update_view, data]
        if use_patch is None:
            use_patch = self.use_patch

        response = self.client.patch(*args) if use_patch else self.client.put(*args)

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            print '\n%s' % response.data

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # getting a fresh copy of the object from DB
        updated = self.object.__class__.objects.get(**{self.lookup_field: object_id})
        # Sanity check:
        # check that the copy in the database was updated as expected.
        self._update_check_db(updated, data, results)

        return response, updated

    def _get_update_name(self):
        if hasattr(self, 'update_name'):
            view_name = self.update_name
        else:
            view_name = self.base_name + self.DETAIL_SUFFIX

        return view_name

    def _update_check_db(self, obj, data, results):
        if results is None:
            results = {}

        for key, value in data.iteritems():
            # check for foreign key
            if hasattr(obj, '%s_id' % key):
                related = getattr(obj, key)
                # hack to check if there's a uuid field and use it instead of pk
                # because of the issue with setting it as primary for Accounts
                if hasattr(related, 'uuid'):
                    attribute = unicode(related.uuid)
                else:
                    attribute = unicode(related.pk)
            else:
                attribute = getattr(obj, key)
                # Handle case of a ManyToMany relation
                if isinstance(attribute, Manager):
                    for pk in value:
                        self.assertIn(pk, [unicode(item.pk) for item in attribute.all()])
                    return True

            self.assertEqual(attribute, results.get(key, value))


class ReadRESTAPITestCaseMixin(ListAPITestCaseMixin, DetailAPITestCaseMixin):

    """Adds the read CRUD operations tests to the test case.

    Includes: :class:`ListAPITestCaseMixin`, :class:`DetailAPITestCaseMixin`.
    """

    pass


class WriteRESTAPITestCaseMixin(CreateAPITestCaseMixin, UpdateAPITestCaseMixin, DestroyAPITestCaseMixin):

    """Adds the write CRUD operations tests to the test case.

    Includes: :class:`CreateAPITestCaseMixin`, :class:`UpdateAPITestCaseMixin`, :class:`DestroyAPITestCaseMixin`.
    """

    pass


class ReadWriteRESTAPITestCaseMixin(ReadRESTAPITestCaseMixin, WriteRESTAPITestCaseMixin):

    """A complete API test case that covers all successful CRUD operation requests.

    Includes: :class:`ReadRESTAPITestCaseMixin`, :class:`WriteRESTAPITestCaseMixin`.
    """

    pass
