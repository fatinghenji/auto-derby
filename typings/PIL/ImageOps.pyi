from typing import Any, Iterable, Protocol

from .Image import Image, _Resample, _Size

class _Deformer(Protocol):
    def getmesh(self, image: Image): ...

def autocontrast(
    image: Image,
    cutoff: int = ...,
    ignore: int | None = ...,
    mask: Image | None = ...,
    preserve_tone: bool = ...,
) -> Image: ...
def colorize(
    image: Image,
    black: int | str,
    white: int | str,
    mid: int | str | None = ...,
    blackpoint: int = ...,
    whitepoint: int = ...,
    midpoint: int = ...,
) -> Image: ...
def contain(image: Image, size: _Size, method: _Resample = ...) -> Image: ...
def pad(
    image: Image,
    size: _Size,
    method: _Resample = ...,
    color: Any | None = ...,
    centering: Iterable[float] = ...,
) -> Image: ...
def crop(image: Image, border: int = ...) -> Image: ...
def scale(image: Image, factor: float, resample: _Resample = ...) -> Image: ...
def deform(image: Image, deformer: _Deformer, resample: _Resample = ...) -> Image: ...
def equalize(image: Image, mask: Any | None = ...) -> Image: ...
def expand(image: Image, border: int = ..., fill: int = ...) -> Image: ...
def fit(
    image: Image,
    size: _Size,
    method: _Resample = ...,
    bleed: float = ...,
    centering: Iterable[float] = ...,
) -> Image: ...
def flip(image: Image) -> Image: ...
def grayscale(image: Image) -> Image: ...
def invert(image: Image) -> Image: ...
def mirror(image: Image) -> Image: ...
def posterize(image: Image, bits: int) -> Image: ...
def solarize(image: Image, threshold: int = ...) -> Image: ...
def exif_transpose(image: Image) -> Image: ...
