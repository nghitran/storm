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
# --- BEGIN MODIFICATIONS ---
# Date: 2025-07-24
# Modifier: Nghi Tran / ClickMedix
# Reason: Added thread safety locks to EventBus methods (hook, unhook, emit)
#         to prevent "Set changed size during iteration" RuntimeError in concurrent environments.
# --- END MODIFICATIONS ---

from __future__ import print_function

import weakref
import threading

from storm import has_cextensions


__all__ = ["EventSystem"]


class EventSystem(object):
    """A system for managing hooks that are called when events are emitted.

    Hooks are callables that take the event system C{owner} as their first
    argument, followed by the arguments passed when emitting the event,
    followed by any additional C{data} arguments given when registering the
    hook.

    Hooks registered for a given event C{name} are stored without ordering:
    no particular call order may be assumed when an event is emitted.
    """

    def __init__(self, owner):
        """
        @param owner: The object that owns this event system.  It is passed
            as the first argument to each hook function.
        """
        self._owner_ref = weakref.ref(owner)
        self._hooks = {}
        self._lock = threading.RLock()

    def hook(self, name, callback, *data):
        """Register a hook.

        @param name: The name of the event for which this hook should be
            called.
        @param callback: A callable which should be called when the event is
            emitted.
        @param data: Additional arguments to pass to the callable, after the
            C{owner} and any arguments passed when emitting the event.
        """
        with self._lock: # acquire() and release() are handled automatically
            callbacks = self._hooks.get(name)
            if callbacks is None:
                self._hooks.setdefault(name, set()).add((callback, data))
            else:
                callbacks.add((callback, data))

    def unhook(self, name, callback, *data):
        """Unregister a hook.

        This ignores attempts to unregister hooks that were not already
        registered.

        @param name: The name of the event for which this hook should no
            longer be called.
        @param callback: The callable to unregister.
        @param data: Additional arguments that were passed when registering
            the callable.
        """
        with self._lock: # acquire() and release() are handled automatically
            callbacks = self._hooks.get(name)
            if callbacks is not None:
                callbacks.discard((callback, data))

    def emit(self, name, *args):
        """Emit an event, calling any registered hooks.

        @param name: The name of the event.
        @param args: Additional arguments to pass to hooks.
        """
        owner = self._owner_ref()
        callbacks_to_execute = []
        callbacks_to_remove = []
        if owner is not None:
            with self._lock: # Acquire lock to safely copy the current set of callbacks
                callbacks = self._hooks.get(name)
                if callbacks:
                    # Create a list copy of the current (callback, data) tuples
                    # *under the lock* to ensure thread-safe snapshotting.
                    callbacks_to_execute = list(callbacks)

            # Release the lock BEFORE executing callbacks.
            for callback, data in callbacks_to_execute:
                try:
                    if callback(owner, *(args + data)) is False:
                        callbacks_to_remove.append((callback, data))
                except Exception as e:
                    print "Error executing callback '%s' for event '%s': %s" % (callback.__name__ if hasattr(callback, '__name__') else str(callback), name, e)
                    import traceback
                    traceback.print_exc()

            # Perform actual removal from the original set (under lock)
            if callbacks_to_remove:
                with self._lock: # Lock required for modification
                    current_callbacks = self._hooks.get(name)
                    if current_callbacks: # Check if event still exists (might be unhooked by another thread)
                        for item_to_remove in callbacks_to_remove:
                            current_callbacks.discard(item_to_remove)
                        if not current_callbacks:
                            del self._hooks[name]


if has_cextensions:
    from storm.cextensions import EventSystem
