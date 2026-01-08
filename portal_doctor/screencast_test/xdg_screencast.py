"""XDG ScreenCast portal test via DBus.

Implements the full ScreenCast flow:
CreateSession → SelectSources → Start
"""

import asyncio
import re
from typing import Optional

from dbus_next.aio import MessageBus
from dbus_next import BusType, Variant
from dbus_next.errors import DBusError
import dbus_next.validators

from ..models import ScreenCastTestResult

# Patch dbus-next to allow hyphens in member names (e.g. "power-saver-enabled" property)
# This fixes the upstream bug: https://github.com/altdesktop/python-dbus-next/issues/92
dbus_next.validators._element_re = re.compile(r'^[A-Za-z_][A-Za-z0-9_-]*$')


# Portal interface path
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
SCREENCAST_IFACE = "org.freedesktop.portal.ScreenCast"
REQUEST_IFACE = "org.freedesktop.portal.Request"


class ScreenCastTest:
    """Runs the XDG ScreenCast portal test flow."""
    
    def __init__(self):
        self.bus: Optional[MessageBus] = None
        self.request_token_counter = 0
        self.session_handle: Optional[str] = None
        
    async def connect(self) -> bool:
        """Connect to the session bus."""
        try:
            self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
            return True
        except Exception as e:
            return False
    
    async def disconnect(self):
        """Disconnect from the bus."""
        if self.bus:
            self.bus.disconnect()
            self.bus = None
    
    def _get_request_token(self) -> str:
        """Generate a unique request token."""
        self.request_token_counter += 1
        return f"portal_doctor_{self.request_token_counter}"
    
    def _get_request_path(self, token: str) -> str:
        """Get the request object path for a token."""
        if not self.bus:
            return ""
        sender = self.bus.unique_name.replace(".", "_").replace(":", "")
        return f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
    
    async def _wait_for_response(self, request_path: str, timeout: float = 60.0) -> tuple[int, dict]:
        """Wait for a Response signal on a request object.
        
        Returns:
            Tuple of (response_code, results_dict)
            response_code: 0 = success, 1 = cancelled, 2 = error
        """
        if not self.bus:
            raise RuntimeError("Not connected to bus")
        
        response_received = asyncio.Event()
        response_data: list = [2, {}]  # Default to error
        
        def on_response(response: int, results: dict):
            response_data[0] = response
            response_data[1] = results
            response_received.set()
        
        try:
            # Get the request object and connect to Response signal
            introspection = await self.bus.introspect(PORTAL_BUS_NAME, request_path)
            
            proxy = self.bus.get_proxy_object(PORTAL_BUS_NAME, request_path, introspection)
            request_iface = proxy.get_interface(REQUEST_IFACE)
            
            request_iface.on_response(on_response)
            
            # Wait for response with timeout
            await asyncio.wait_for(response_received.wait(), timeout=timeout)
            
            return response_data[0], response_data[1]
            
        except asyncio.TimeoutError:
            raise TimeoutError(f"Timeout waiting for portal response on {request_path}")
    
    async def run_test(self) -> ScreenCastTestResult:
        """Run the complete ScreenCast test flow.
        
        Returns:
            ScreenCastTestResult with test outcome
        """
        step = "Initialize"
        
        try:
            # Connect to bus
            step = "Connect"
            if not await self.connect():
                return ScreenCastTestResult(
                    success=False,
                    step_reached=step,
                    error_name="ConnectionError",
                    error_message="Failed to connect to DBus session bus",
                )
            
            # Get portal proxy
            step = "GetPortal"
            introspection = await self.bus.introspect(PORTAL_BUS_NAME, PORTAL_OBJECT_PATH)
            
            proxy = self.bus.get_proxy_object(PORTAL_BUS_NAME, PORTAL_OBJECT_PATH, introspection)
            screencast = proxy.get_interface(SCREENCAST_IFACE)
            
            # Step 1: CreateSession
            step = "CreateSession"
            session_token = self._get_request_token()
            request_token = self._get_request_token()
            request_path = self._get_request_path(request_token)
            
            options = {
                "handle_token": Variant("s", request_token),
                "session_handle_token": Variant("s", session_token),
            }
            
            await screencast.call_create_session(options)
            
            response_code, results = await self._wait_for_response(request_path, timeout=10.0)
            
            if response_code != 0:
                return ScreenCastTestResult(
                    success=False,
                    step_reached=step,
                    error_name="CreateSessionFailed",
                    error_message=f"CreateSession returned code {response_code}",
                )
            
            session_handle = results.get("session_handle")
            if not session_handle:
                return ScreenCastTestResult(
                    success=False,
                    step_reached=step,
                    error_name="NoSessionHandle",
                    error_message="CreateSession did not return a session handle",
                )
            
            # Unwrap Variant if needed
            if isinstance(session_handle, Variant):
                session_handle = session_handle.value
            
            self.session_handle = session_handle
            
            # Step 2: SelectSources
            step = "SelectSources"
            request_token = self._get_request_token()
            request_path = self._get_request_path(request_token)
            
            source_options = {
                "handle_token": Variant("s", request_token),
                "types": Variant("u", 1 | 2),  # MONITOR | WINDOW
                "multiple": Variant("b", False),
            }
            
            await screencast.call_select_sources(session_handle, source_options)
            
            # This typically shows the picker dialog
            response_code, results = await self._wait_for_response(request_path, timeout=120.0)
            
            if response_code == 1:
                return ScreenCastTestResult(
                    success=False,
                    step_reached=step,
                    error_name="UserCancelled",
                    error_message="User cancelled the source selection",
                )
            elif response_code != 0:
                return ScreenCastTestResult(
                    success=False,
                    step_reached=step,
                    error_name="SelectSourcesFailed",
                    error_message=f"SelectSources returned code {response_code}",
                )
            
            # Step 3: Start
            step = "Start"
            request_token = self._get_request_token()
            request_path = self._get_request_path(request_token)
            
            start_options = {
                "handle_token": Variant("s", request_token),
            }
            
            # parent_window can be empty string for no parent
            await screencast.call_start(session_handle, "", start_options)
            
            response_code, results = await self._wait_for_response(request_path, timeout=30.0)
            
            if response_code == 1:
                return ScreenCastTestResult(
                    success=False,
                    step_reached=step,
                    error_name="UserCancelled",
                    error_message="User cancelled the start request",
                )
            elif response_code != 0:
                return ScreenCastTestResult(
                    success=False,
                    step_reached=step,
                    error_name="StartFailed",
                    error_message=f"Start returned code {response_code}",
                )
            
            # Extract stream info
            streams = results.get("streams")
            pipewire_node_id = None
            stream_properties = None
            
            if streams:
                if isinstance(streams, Variant):
                    streams = streams.value
                if streams and len(streams) > 0:
                    stream = streams[0]
                    if isinstance(stream, tuple) and len(stream) >= 2:
                        pipewire_node_id = stream[0]
                        stream_properties = stream[1] if len(stream) > 1 else {}
            
            return ScreenCastTestResult(
                success=True,
                step_reached="Complete",
                pipewire_node_id=pipewire_node_id,
                stream_properties=stream_properties,
                log_excerpt=f"Successfully obtained stream with node ID: {pipewire_node_id}",
            )
            
        except DBusError as e:
            return ScreenCastTestResult(
                success=False,
                step_reached=step,
                error_name=e.type,
                error_message=str(e),
            )
        except TimeoutError as e:
            return ScreenCastTestResult(
                success=False,
                step_reached=step,
                error_name="Timeout",
                error_message=str(e),
            )
        except Exception as e:
            return ScreenCastTestResult(
                success=False,
                step_reached=step,
                error_name=type(e).__name__,
                error_message=str(e),
            )
        finally:
            await self.disconnect()


async def run_screencast_test() -> ScreenCastTestResult:
    """Run the screencast test.
    
    This is the main entry point for the screencast test.
    
    Returns:
        ScreenCastTestResult with the test outcome
    """
    test = ScreenCastTest()
    return await test.run_test()


def run_screencast_test_sync() -> ScreenCastTestResult:
    """Synchronous wrapper for running the screencast test.
    
    Returns:
        ScreenCastTestResult with the test outcome
    """
    try:
        return asyncio.run(run_screencast_test())
    except Exception as e:
        return ScreenCastTestResult(
            success=False,
            step_reached="Initialize",
            error_name=type(e).__name__,
            error_message=str(e),
        )
