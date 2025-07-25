Infoheritance
=============

Storm doesn't support classes that have columns in multiple tables.  This
makes using inheritance rather difficult.  The infoheritance pattern described
here provides a way to get the benefits of inheritance without running into
the problems Storm has with multi-table classes.


Defining a sample model
-----------------------

Let's consider an inheritance hierarchy to migrate to Storm.

.. code-block:: python

    class Person(object):

        def __init__(self, name):
            self.name = name


    class SecretAgent(Person):

        def __init__(self, name, passcode):
            super(SecretAgent, self).__init__(name)
            self.passcode = passcode


    class Teacher(Person):

        def __init__(self, name, school):
            super(Employee, self).__init__(name):
            self.school = school

We want to use three tables to store data for these objects: ``person``,
``secret_agent`` and ``teacher``.  We can't simply convert instance
attributes to Storm properties and add ``__storm_table__`` definitions
because a single object may not have columns that come from more than one
table.  We can't have ``Teacher`` getting its ``name`` column from the
``person`` table and its ``school`` column from the ``teacher`` table, for
example.


The infoheritance pattern
-------------------------

The infoheritance pattern uses composition instead of inheritance to work
around the multiple table limitation.  A base Storm class is used to represent
all objects in the hierarchy.  Each instance of this base class has an info
property that yields an instance of a specific info class.  An info class
provides the additional data and behaviour you'd normally implement in a
subclass.  Following is the design from above converted to use the pattern.

.. doctest::

    >>> from storm.locals import Storm, Store, Int, Unicode, Reference

    >>> person_info_types = {}

    >>> def register_person_info_type(info_type, info_class):
    ...     existing_info_class = person_info_types.get(info_type)
    ...     if existing_info_class is not None:
    ...         raise RuntimeError("%r has the same info_type of %r" %
    ...                            (info_class, existing_info_class))
    ...     person_info_types[info_type] = info_class
    ...     info_class.info_type = info_type


    >>> class Person(Storm):
    ...
    ...     __storm_table__ = "person"
    ...
    ...     id = Int(allow_none=False, primary=True)
    ...     name = Unicode(allow_none=False)
    ...     info_type = Int(allow_none=False)
    ...     _info = None
    ...
    ...     def __init__(self, store, name, info_class, **kwargs):
    ...         self.name = name
    ...         self.info_type = info_class.info_type
    ...         store.add(self)
    ...         self._info = info_class(self, **kwargs)
    ...
    ...     @property
    ...     def info(self):
    ...         if self._info is not None:
    ...             return self._info
    ...         assert self.id is not None
    ...         info_class = person_info_types[self.info_type]
    ...         if not hasattr(info_class, "__storm_table__"):
    ...             info = info_class.__new__(info_class)
    ...             info.person = self
    ...         else:
    ...             info = Store.of(self).get(info_class, self.id)
    ...         self._info = info
    ...         return info


    >>> class PersonInfo(object):
    ...
    ...     def __init__(self, person):
    ...         self.person = person


    >>> class StoredPersonInfo(PersonInfo):
    ...
    ...     person_id = Int(allow_none=False, primary=True)
    ...     person = Reference(person_id, Person.id)


    >>> class SecretAgent(StoredPersonInfo):
    ...
    ...     __storm_table__ = "secret_agent"
    ...
    ...     passcode = Unicode(allow_none=False)
    ...
    ...     def __init__(self, person, passcode=None):
    ...         super(SecretAgent, self).__init__(person)
    ...         self.passcode = passcode


    >>> class Teacher(StoredPersonInfo):
    ...
    ...     __storm_table__ = "teacher"
    ...
    ...     school = Unicode(allow_none=False)
    ...
    ...     def __init__(self, person, school=None):
    ...         super(Teacher, self).__init__(person)
    ...         self.school = school

The pattern works by having a base class, ``Person``, keep a reference to an
info class, ``PersonInfo``.  Info classes need to be registered so that
``Person`` can discover them and load them when necessary.  Note that info
types have the same ID as their parent object.  This isn't strictly
necessary, but it makes certain things easy, such as being able to look up
info objects directly by ID when given a person object.  ``Person`` objects
are required to be in a store to ensure that an ID is available and can used
by the info class.


Registering info classes
------------------------

Let's register our info classes.  Each class must be registered with a unique
info type key.  This key is stored in the database, so be sure to use a stable
value.

.. doctest::

    >>> register_person_info_type(1, SecretAgent)
    >>> register_person_info_type(2, Teacher)

Let's create a database to store person objects before we continue.

.. doctest::

    >>> from storm.locals import create_database

    >>> database = create_database("sqlite:")
    >>> store = Store(database)
    >>> result = store.execute("""
    ...     CREATE TABLE person (
    ...         id INTEGER PRIMARY KEY,
    ...         info_type INTEGER NOT NULL,
    ...         name TEXT NOT NULL)
    ... """)
    >>> result = store.execute("""
    ...     CREATE TABLE secret_agent (
    ...         person_id INTEGER PRIMARY KEY,
    ...         passcode TEXT NOT NULL)
    ... """)
    >>> result = store.execute("""
    ...     CREATE TABLE teacher (
    ...         person_id INTEGER PRIMARY KEY,
    ...         school TEXT NOT NULL)
    ... """)


Creating info classes
---------------------

We can easily create person objects now.

.. doctest::

    >>> secret_agent = Person(store, u"Dick Tracy",
    ...                       SecretAgent, passcode=u"secret!")
    >>> teacher = Person(store, u"Mrs. Cohen",
    ...                  Teacher, school=u"Cameron Elementary School")
    >>> store.commit()

And we can easily find them again.

.. doctest::

    >>> del secret_agent
    >>> del teacher
    >>> store.rollback()

    >>> [type(person.info)
    ...  for person in store.find(Person).order_by(Person.name)]
    [<class '...SecretAgent'>, <class '...Teacher'>]


Retrieving info classes
-----------------------

Now that we have our basic hierarchy in place we're going to want to
retrieve objects by info type.  Let's implement a function to make finding
``Person``\ s easier.

.. doctest::

    >>> def get_persons(store, info_classes=None):
    ...     where = []
    ...     if info_classes:
    ...         info_types = [
    ...             info_class.info_type for info_class in info_classes]
    ...         where = [Person.info_type.is_in(info_types)]
    ...     result = store.find(Person, *where)
    ...     result.order_by(Person.name)
    ...     return result

    >>> secret_agent = get_persons(store, info_classes=[SecretAgent]).one()
    >>> print(secret_agent.name)
    Dick Tracy
    >>> print(secret_agent.info.passcode)
    secret!

    >>> teacher = get_persons(store, info_classes=[Teacher]).one()
    >>> print(teacher.name)
    Mrs. Cohen
    >>> print(teacher.info.school)
    Cameron Elementary School

Great, we can easily find different kinds of ``Person``\ s.


In-memory info objects
----------------------

This design also allows for in-memory info objects.  Let's add one to our
hierarchy.

.. doctest::

    >>> class Ghost(PersonInfo):
    ...
    ...     friendly = True

    >>> register_person_info_type(3, Ghost)

We create and load in-memory objects the same way we do stored ones.

.. doctest::

    >>> ghost = Person(store, u"Casper", Ghost)
    >>> store.commit()
    >>> del ghost
    >>> store.rollback()

    >>> ghost = get_persons(store, info_classes=[Ghost]).one()
    >>> print(ghost.name)
    Casper
    >>> print(ghost.info.friendly)
    True

This pattern is very handy when using Storm with code that would naturally be
implemented using inheritance.

..
    >>> Person._storm_property_registry.clear()
