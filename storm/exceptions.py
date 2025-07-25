#
# Copyright (c) 2006, 2007 Canonical
#
# Written by Gustavo Niemeyer <gustavo@niemeyer.net>
#
# This file is part of Storm Object Relational Mapper.
#
# Storm is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 2.1 of
# the License, or (at your option) any later version.
#
# Storm is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from __future__ import print_function

from contextlib import contextmanager
import sys

import six


class StormError(Exception):
    pass


class CompileError(StormError):
    pass

class NoTableError(CompileError):
    pass

class ExprError(StormError):
    pass

class NoneError(StormError):
    pass

class PropertyPathError(StormError):
    pass

class ClassInfoError(StormError):
    pass


class URIError(StormError):
    pass


class ClosedError(StormError):
    pass

class FeatureError(StormError):
    pass

class DatabaseModuleError(StormError):
    pass


class StoreError(StormError):
    pass

class NoStoreError(StormError):
    pass

class WrongStoreError(StoreError):
    pass

class NotFlushedError(StoreError):
    pass

class OrderLoopError(StoreError):
    pass

class NotOneError(StoreError):
    pass

class UnorderedError(StoreError):
    pass

class LostObjectError(StoreError):
    pass


class Error(StormError):
    pass

class Warning(StormError):
    pass

class InterfaceError(Error):
    pass

class DatabaseError(Error):
    pass

class InternalError(DatabaseError):
    pass

class OperationalError(DatabaseError):
    pass

class ProgrammingError(DatabaseError):
    pass

class IntegrityError(DatabaseError):
    pass

class DataError(DatabaseError):
    pass

class NotSupportedError(DatabaseError):
    pass


class DisconnectionError(OperationalError):
    pass


class TimeoutError(StormError):
    """Raised by timeout tracers when remining time is over."""

    def __init__(self, statement, params, message=None):
        self.statement = statement
        self.params = params
        self.message = message

    def __str__(self):
        return ', '.join(
            [repr(element) for element in
             (self.message, self.statement, self.params)
             if element is not None])


class ConnectionBlockedError(StormError):
    """Raised when an attempt is made to use a blocked connection."""


# More generic exceptions must come later.  For convenience, use the order
# of definition above and then reverse it.
_wrapped_exception_types = tuple(reversed((
    Error,
    Warning,
    InterfaceError,
    DatabaseError,
    InternalError,
    OperationalError,
    ProgrammingError,
    IntegrityError,
    DataError,
    NotSupportedError,
    )))


@contextmanager
def wrap_exceptions(database):
    """Context manager that re-raises DB exceptions as StormError instances."""
    try:
        yield
    except Exception as e:
        module = database._exception_module
        if module is None:
            # This backend does not support re-raising database exceptions.
            raise
        for wrapper_type in _wrapped_exception_types:
            dbapi_type = getattr(module, wrapper_type.__name__, None)
            if (dbapi_type is not None and
                    isinstance(dbapi_type, six.class_types) and
                    isinstance(e, dbapi_type)):
                wrapped = database._wrap_exception(wrapper_type, e)
                tb = sys.exc_info()[2]
                # As close to "raise wrapped.with_traceback(tb) from e" as
                # we can manage, but without causing syntax errors on
                # various versions of Python.
                try:
                    if six.PY2:
                        six.reraise(wrapped, None, tb)
                    else:
                        six.raise_from(wrapped.with_traceback(tb), e)
                finally:
                    # Avoid traceback reference cycles.
                    del wrapped, tb
        raise
