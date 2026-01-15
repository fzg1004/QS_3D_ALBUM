"""Convert teaser.ply to match train.ply schema.

- Input teaser.ply: vertex has x,y,z,f_dc_0..2,opacity,scale_0..2,rot_0..3 plus extra elements.
- Output converted.ply: ONLY one element `vertex` with the same properties/order as train.ply:
  x y z nx ny nz f_dc_0 f_dc_1 f_dc_2 f_rest_0..44 opacity scale_0..2 rot_0..3

Defaults:
- nx,ny,nz = 0
- f_rest_0..44 = 0

The output is binary_little_endian 1.0.
"""

from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class PlyHeader:
    format: str
    version: str
    vertex_count: int
    vertex_properties: List[Tuple[str, str]]  # (type, name)
    header_lines: List[str]
    data_start_offset: int


_PLY_TYPE_TO_STRUCT = {
    "char": "b",
    "int8": "b",
    "uchar": "B",
    "uint8": "B",
    "short": "h",
    "int16": "h",
    "ushort": "H",
    "uint16": "H",
    "int": "i",
    "int32": "i",
    "uint": "I",
    "uint32": "I",
    "float": "f",
    "float32": "f",
    "double": "d",
    "float64": "d",
}


def _readline_ascii(f) -> bytes:
    line = f.readline()
    if not line:
        raise EOFError("Unexpected EOF while reading PLY header")
    return line


def parse_ply_header(path: Path) -> PlyHeader:
    with path.open("rb") as f:
        header_bytes: List[bytes] = []
        header_lines: List[str] = []

        first = _readline_ascii(f)
        header_bytes.append(first)
        header_lines.append(first.decode("ascii", errors="strict").rstrip("\r\n"))
        if header_lines[0].strip() != "ply":
            raise ValueError(f"Not a PLY file: {path}")

        fmt_line = _readline_ascii(f)
        header_bytes.append(fmt_line)
        fmt_parts = fmt_line.decode("ascii", errors="strict").strip().split()
        if len(fmt_parts) != 3 or fmt_parts[0] != "format":
            raise ValueError(f"Invalid format line in header: {fmt_line!r}")
        fmt, version = fmt_parts[1], fmt_parts[2]
        header_lines.append(fmt_line.decode("ascii", errors="strict").rstrip("\r\n"))

        vertex_count = None
        vertex_properties: List[Tuple[str, str]] = []
        in_vertex = False

        while True:
            pos_before = f.tell()
            bline = _readline_ascii(f)
            header_bytes.append(bline)
            line = bline.decode("ascii", errors="strict").rstrip("\r\n")
            header_lines.append(line)

            stripped = line.strip()
            if stripped == "end_header":
                data_start = f.tell()
                break

            parts = stripped.split()
            if not parts:
                continue

            if parts[0] == "element":
                if len(parts) != 3:
                    raise ValueError(f"Invalid element line: {line}")
                elem_name = parts[1]
                elem_count = int(parts[2])
                in_vertex = elem_name == "vertex"
                if in_vertex:
                    vertex_count = elem_count
                continue

            if parts[0] == "property":
                if in_vertex:
                    # Only support scalar properties for vertex (no list)
                    if len(parts) == 3:
                        p_type, p_name = parts[1], parts[2]
                    elif len(parts) >= 5 and parts[1] == "list":
                        raise ValueError(
                            "List properties are not supported for vertex in this converter. "
                            f"Found: {line}"
                        )
                    else:
                        raise ValueError(f"Invalid property line: {line}")
                    vertex_properties.append((p_type, p_name))
                continue

        if vertex_count is None:
            raise ValueError(f"No vertex element found in header: {path}")

        return PlyHeader(
            format=fmt,
            version=version,
            vertex_count=vertex_count,
            vertex_properties=vertex_properties,
            header_lines=header_lines,
            data_start_offset=data_start,
        )


def _struct_for_vertex(props: Sequence[Tuple[str, str]], endian: str) -> struct.Struct:
    try:
        fmt = endian + "".join(_PLY_TYPE_TO_STRUCT[t] for t, _ in props)
    except KeyError as e:
        raise ValueError(f"Unsupported PLY scalar type: {e}") from e
    return struct.Struct(fmt)


def _endian_for_format(fmt: str) -> str:
    if fmt == "binary_little_endian":
        return "<"
    if fmt == "binary_big_endian":
        return ">"
    raise ValueError(f"Unsupported PLY format for binary parsing: {fmt}")


def read_vertex_table_binary(path: Path, header: PlyHeader) -> dict[str, np.ndarray]:
    if header.format not in ("binary_little_endian", "binary_big_endian"):
        raise ValueError(
            f"Only binary PLY is supported by this converter. Got: {header.format}"
        )

    endian = _endian_for_format(header.format)
    st = _struct_for_vertex(header.vertex_properties, endian)

    arrays: dict[str, np.ndarray] = {}
    for p_type, p_name in header.vertex_properties:
        # Map all numeric scalar properties to float32 for output consistency
        arrays[p_name] = np.empty((header.vertex_count,), dtype=np.float32)

    with path.open("rb") as f:
        f.seek(header.data_start_offset)
        for i in range(header.vertex_count):
            chunk = f.read(st.size)
            if len(chunk) != st.size:
                raise EOFError(
                    f"Unexpected EOF while reading vertex data at {i}/{header.vertex_count}"
                )
            values = st.unpack(chunk)
            for (p_type, p_name), v in zip(header.vertex_properties, values):
                arrays[p_name][i] = float(v)

    return arrays


def write_ply_binary_vertex_only(
    path: Path,
    vertex_count: int,
    schema: Sequence[Tuple[str, str]],
    columns: dict[str, np.ndarray],
) -> None:
    # Always write little endian float/uint/uchar as given in schema
    header_lines: List[str] = [
        "ply",
        "format binary_little_endian 1.0",
        f"element vertex {vertex_count}",
    ]
    for p_type, p_name in schema:
        header_lines.append(f"property {p_type} {p_name}")
    header_lines.append("end_header")
    header = "\n".join(header_lines) + "\n"

    endian = "<"
    st = _struct_for_vertex(schema, endian)

    # Sanity check
    for _, p_name in schema:
        if p_name not in columns:
            raise KeyError(f"Missing column for output: {p_name}")
        if columns[p_name].shape[0] != vertex_count:
            raise ValueError(
                f"Column {p_name} has {columns[p_name].shape[0]} rows, expected {vertex_count}"
            )

    with path.open("wb") as f:
        f.write(header.encode("ascii"))
        for i in range(vertex_count):
            row = [columns[name][i] for _, name in schema]
            f.write(st.pack(*row))


def build_target_schema_from_train_header(train_header: PlyHeader) -> List[Tuple[str, str]]:
    # Keep exactly the vertex properties defined in train.ply (type + name + order)
    #return list(train_header.vertex_properties)
    # If you want to use a fixed target schema regardless of the provided train header,
    # return the explicit schema expected by downstream code.
    return [
        ('float', 'x'), ('float', 'y'), ('float', 'z'),
        ('float', 'nx'), ('float', 'ny'), ('float', 'nz'),
        ('float', 'f_dc_0'), ('float', 'f_dc_1'), ('float', 'f_dc_2'),
        ('float', 'f_rest_0'), ('float', 'f_rest_1'), ('float', 'f_rest_2'), ('float', 'f_rest_3'),
        ('float', 'f_rest_4'), ('float', 'f_rest_5'), ('float', 'f_rest_6'), ('float', 'f_rest_7'),
        ('float', 'f_rest_8'), ('float', 'f_rest_9'), ('float', 'f_rest_10'), ('float', 'f_rest_11'),
        ('float', 'f_rest_12'), ('float', 'f_rest_13'), ('float', 'f_rest_14'), ('float', 'f_rest_15'),
        ('float', 'f_rest_16'), ('float', 'f_rest_17'), ('float', 'f_rest_18'), ('float', 'f_rest_19'),
        ('float', 'f_rest_20'), ('float', 'f_rest_21'), ('float', 'f_rest_22'), ('float', 'f_rest_23'),
        ('float', 'f_rest_24'), ('float', 'f_rest_25'), ('float', 'f_rest_26'), ('float', 'f_rest_27'),
        ('float', 'f_rest_28'), ('float', 'f_rest_29'), ('float', 'f_rest_30'), ('float', 'f_rest_31'),
        ('float', 'f_rest_32'), ('float', 'f_rest_33'), ('float', 'f_rest_34'), ('float', 'f_rest_35'),
        ('float', 'f_rest_36'), ('float', 'f_rest_37'), ('float', 'f_rest_38'), ('float', 'f_rest_39'),
        ('float', 'f_rest_40'), ('float', 'f_rest_41'), ('float', 'f_rest_42'), ('float', 'f_rest_43'),
        ('float', 'f_rest_44'),
        ('float', 'opacity'),
        ('float', 'scale_0'), ('float', 'scale_1'), ('float', 'scale_2'),
        ('float', 'rot_0'), ('float', 'rot_1'), ('float', 'rot_2'), ('float', 'rot_3'),
    ]


def convert(teaser_path: Path, train_path: Path, output_path: Path) -> None:
    teaser_header = parse_ply_header(teaser_path)
    #train_header = parse_ply_header(train_path)

    target_schema = build_target_schema_from_train_header(None)

    # Read teaser vertex data (only properties in teaser's vertex element)
    teaser_cols = read_vertex_table_binary(teaser_path, teaser_header)

    # Build output columns according to train schema
    out_cols: dict[str, np.ndarray] = {}
    n = teaser_header.vertex_count

    for p_type, name in target_schema:
        if name in teaser_cols:
            out_cols[name] = teaser_cols[name].astype(np.float32, copy=False)
        else:
            # Fill missing fields per agreed strategy
            out_cols[name] = np.zeros((n,), dtype=np.float32)

    # Explicitly ensure missing normals and f_rest_* are zero (even if schema changes)
    for name in ("nx", "ny", "nz"):
        if name in out_cols and name not in teaser_cols:
            out_cols[name].fill(0.0)
    for i in range(45):
        name = f"f_rest_{i}"
        if name in out_cols and name not in teaser_cols:
            out_cols[name].fill(0.0)

    # Write converted PLY: vertex-only, train schema/order, little endian
    write_ply_binary_vertex_only(output_path, n, target_schema, out_cols)


def _summarize_header(path: Path) -> str:
    h = parse_ply_header(path)
    props = ", ".join([name for _t, name in h.vertex_properties])
    return (
        f"{path.name}: format={h.format} vertex={h.vertex_count} props={len(h.vertex_properties)}\n"
        f"  [{props}]"
    )


def main(argv: Sequence[str] | None = None) -> int:

    ap = argparse.ArgumentParser(description="Convert teaser.ply to match train.ply schema")
    ap.add_argument(
        "--teaser",
        type=Path,
        default=Path("PLY") / "teaser.ply",
        help="Input teaser.ply path",
    )
    ap.add_argument(
        "--train",
        type=Path,
        default=Path("PLY") / "train.ply",
        help="Reference train.ply path (schema source)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("PLY") / "converted.ply",
        help="Output converted.ply path",
    )
    args = ap.parse_args(argv)

    convert(args.teaser, args.train, args.out)

    print(_summarize_header(args.train))
    print(_summarize_header(args.teaser))
    print(_summarize_header(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
