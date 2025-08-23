from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    Integer,
    Float,
    JSON,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint,
)
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Manufacturer(Base):
    __tablename__ = "manufacturers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    homepage: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    manufacturer_id: Mapped[int] = mapped_column(ForeignKey("manufacturers.id"))
    segment_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(200))
    product_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    manufacturer: Mapped["Manufacturer"] = relationship()
    __table_args__ = (
        UniqueConstraint(
            "manufacturer_id", "segment_id", "name", name="uq_vendor_seg_model"
        ),
    )


class RawDocument(Base):
    __tablename__ = "raw_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    http_status: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    content_type: Mapped[str | None] = mapped_column(String(32))  # html|pdf_text
    text: Mapped[str] = mapped_column(Text)
    raw_specs: Mapped[dict | None] = mapped_column(JSON)
    content_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256 hash
    file_path: Mapped[str | None] = mapped_column(String(500))  # Local cache path for PDFs


class NormalizedSpec(Base):
    __tablename__ = "normalized_specs"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    snapshot_ts: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    wavelength_nm: Mapped[float | None] = mapped_column(Float)
    output_power_mw_nominal: Mapped[float | None] = mapped_column(Float)
    output_power_mw_min: Mapped[float | None] = mapped_column(Float)
    rms_noise_pct: Mapped[float | None] = mapped_column(Float)
    power_stability_pct: Mapped[float | None] = mapped_column(Float)
    linewidth_mhz: Mapped[float | None] = mapped_column(Float)
    linewidth_nm: Mapped[float | None] = mapped_column(Float)
    m2: Mapped[float | None] = mapped_column(Float)
    beam_diameter_mm: Mapped[float | None] = mapped_column(Float)
    beam_divergence_mrad: Mapped[float | None] = mapped_column(Float)
    polarization: Mapped[str | None] = mapped_column(String(64))
    modulation_analog_hz: Mapped[float | None] = mapped_column(Float)
    modulation_digital_hz: Mapped[float | None] = mapped_column(Float)
    ttl_shutter: Mapped[bool | None] = mapped_column()
    fiber_output: Mapped[bool | None] = mapped_column()
    fiber_na: Mapped[float | None] = mapped_column(Float)
    fiber_mfd_um: Mapped[float | None] = mapped_column(Float)
    warmup_time_min: Mapped[float | None] = mapped_column(Float)
    interfaces: Mapped[list | None] = mapped_column(JSON)
    dimensions_mm: Mapped[dict | None] = mapped_column(JSON)
    vendor_fields: Mapped[dict | None] = mapped_column(JSON)
    source_raw_id: Mapped[int | None] = mapped_column(Integer)
