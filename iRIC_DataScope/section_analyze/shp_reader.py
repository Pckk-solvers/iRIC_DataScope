from __future__ import annotations

from pathlib import Path

import shapefile

from iRIC_DataScope.section_analyze.models import SectionAnalyzeOptions, SectionLine


def _pick_field(fields: list[str], preferred: str | None) -> str | None:
    if preferred:
        if preferred not in fields:
            raise ValueError(f"SHP属性フィールドが見つかりません: {preferred}")
        return preferred
    return None


def _to_value(record: shapefile._Record, field: str | None) -> str | None:
    if not field:
        return None
    value = record.as_dict().get(field)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def list_shp_fields(shp_path: Path) -> list[str]:
    path = Path(shp_path)
    if not path.is_file():
        raise FileNotFoundError(f"側線SHPが見つかりません: {path}")
    reader = shapefile.Reader(str(path), encoding="utf-8")
    return [field[0] for field in reader.fields[1:]]


def read_section_lines(shp_path: Path, options: SectionAnalyzeOptions) -> list[SectionLine]:
    path = Path(shp_path)
    if not path.is_file():
        raise FileNotFoundError(f"側線SHPが見つかりません: {path}")

    reader = shapefile.Reader(str(path), encoding="utf-8")
    fields = [field[0] for field in reader.fields[1:]]
    id_field = _pick_field(fields, options.section_id_field)
    name_field = _pick_field(fields, options.section_name_field)
    if not name_field:
        raise ValueError("断面名属性を指定してください。")

    lines: list[SectionLine] = []
    for idx, shape_record in enumerate(reader.iterShapeRecords(), start=1):
        shape = shape_record.shape
        if shape.shapeType not in {shapefile.POLYLINE, shapefile.POLYLINEZ, shapefile.POLYLINEM}:
            raise ValueError(f"LineString以外のジオメトリは未対応です: feature={idx}")
        if len(shape.parts) != 1:
            raise ValueError(f"MultiLineString相当の複数partは未対応です: feature={idx}")
        points = tuple((float(x), float(y)) for x, y in shape.points)
        if len(points) < 2:
            raise ValueError(f"側線は2点以上必要です: feature={idx}")

        section_id = _to_value(shape_record.record, id_field) or f"SEC{idx:03d}"
        section_name = _to_value(shape_record.record, name_field)
        if not section_name:
            raise ValueError(f"断面名属性が空です: feature={idx}, field={name_field}")
        order_no = idx
        record_dict = shape_record.record.as_dict()
        if "order_no" in record_dict:
            try:
                order_no = int(record_dict["order_no"])
            except Exception:
                order_no = idx

        lines.append(
            SectionLine(
                section_id=section_id,
                section_name=section_name,
                source_feature_id=idx,
                order_no=order_no,
                points=points,
            )
        )
    if not lines:
        raise ValueError(f"側線SHPにfeatureがありません: {path}")
    return sorted(lines, key=lambda line: (line.order_no, line.source_feature_id))
