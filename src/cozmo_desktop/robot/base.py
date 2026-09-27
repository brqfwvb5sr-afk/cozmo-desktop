"""Backend contract. Distances in mm, wheel speeds in mm/s, angles in degrees."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from PIL import Image


class RobotError(Exception):
    """A recoverable, user-facing robot error (never include secrets)."""


class NotConnectedError(RobotError):
    def __init__(self) -> None:
        super().__init__("Connect to Cozmo first.")


@dataclass(frozen=True)
class CubeState:
    number: int
    connected: bool = False
    tapped: bool = False
    moved: bool = False
    orientation: str = "unknown"


@dataclass(frozen=True)
class RobotState:
    connected: bool = False
    battery: float | None = 87.0
    battery_voltage: float | None = None
    backend_name: str = "simulator"
    motors_enabled: bool = True
    safety_status: str = ""
    charging: bool = False
    head_angle: float = 0.0
    lift_height: float = 0.0
    left_speed: float = 0.0
    right_speed: float = 0.0
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0
    expression: str = "Neutral"
    animation: str | None = None
    speech: str = ""
    freeplay: bool = False
    camera_available: bool = False
    face_detected: bool = False
    cubes: tuple[CubeState, ...] = field(
        default_factory=lambda: tuple(CubeState(n) for n in range(1, 4))
    )


@dataclass(frozen=True)
class Animation:
    name: str
    category: str
    duration: float


class RobotBackend(ABC):
    """No Qt or SDK types cross this boundary.

    Implementations must expire unrenewed wheel commands independently of UI
    refresh, stop on disconnect, and keep stop idempotent even when disconnected.
    Async methods must not block. Long actions must respect task cancellation.
    """

    is_simulation = True
    speed_cap = 80

    async def arm_motors(self) -> None:
        """Explicit opt-in for physical motor commands; simulator needs no arming."""
        return None

    async def cube_lights(self, number: int) -> None:
        raise RobotError("Cube light control is unavailable in this backend.")

    @property
    @abstractmethod
    def state(self) -> RobotState: ...

    @property
    @abstractmethod
    def animations(self) -> tuple[Animation, ...]: ...

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def drive(self, left: float, right: float) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def set_head_angle(self, angle: float) -> None: ...

    @abstractmethod
    async def set_lift_height(self, height: float) -> None: ...

    @abstractmethod
    async def speak(self, text: str) -> None: ...

    @abstractmethod
    async def play_animation(self, animation: str) -> None: ...

    @abstractmethod
    async def display_face(self, frame: Image.Image, name: str = "Custom") -> None: ...

    @abstractmethod
    async def get_camera_frame(self) -> Image.Image: ...

    @abstractmethod
    async def enable_freeplay(self) -> None: ...

    @abstractmethod
    async def disable_freeplay(self) -> None: ...
