"""Decodificador genérico de mensagens protobuf sem .proto (estilo `protoc --decode_raw`).

Uso exploratório: entender a estrutura interna dos arquivos .jdl (log de
máquina John Deere / dados de executados) antes de escrever um parser com
significado semântico.
"""
import sys


def read_varint(buf, pos):
    result = 0
    shift = 0
    start = pos
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def decode_message(buf, pos, end, indent=0, out=None):
    if out is None:
        out = []
    while pos < end:
        tag_start = pos
        tag, pos = read_varint(buf, pos)
        field_no = tag >> 3
        wire_type = tag & 0x7

        if wire_type == 0:  # varint
            val, pos = read_varint(buf, pos)
            out.append(f"{'  '*indent}[{tag_start}] field {field_no} (varint) = {val}")
        elif wire_type == 1:  # fixed64
            val = int.from_bytes(buf[pos:pos+8], "little")
            import struct
            dval = struct.unpack("<d", buf[pos:pos+8])[0]
            out.append(f"{'  '*indent}[{tag_start}] field {field_no} (fixed64) = {val} (double={dval})")
            pos += 8
        elif wire_type == 2:  # length-delimited
            length, pos = read_varint(buf, pos)
            data = buf[pos:pos+length]
            pos += length
            # heurística: tenta como submensagem, senão como string/bytes
            # (estrito: sem tab/newline/CR -- esses bytes de controle são exatamente
            # os primeiros bytes de tags protobuf comuns tipo 0x0a, e permiti-los aqui
            # fazia submensagens reais serem tratadas como string e nunca abertas)
            printable = all(32 <= c < 127 for c in data) and len(data) > 0
            if printable:
                out.append(f"{'  '*indent}[{tag_start}] field {field_no} (bytes, len={length}) = STRING {data!r}")
            else:
                out.append(f"{'  '*indent}[{tag_start}] field {field_no} (bytes, len={length}) = tentando submsg:")
                sub_out = []
                try:
                    decode_message(data, 0, len(data), indent+1, sub_out)
                    if sub_out:
                        out.extend(sub_out)
                    else:
                        out.append(f"{'  '*(indent+1)}RAW {data.hex()}")
                except Exception:
                    out.append(f"{'  '*(indent+1)}RAW {data.hex()}")
        elif wire_type == 5:  # fixed32
            import struct
            val = int.from_bytes(buf[pos:pos+4], "little")
            fval = struct.unpack("<f", buf[pos:pos+4])[0]
            out.append(f"{'  '*indent}[{tag_start}] field {field_no} (fixed32) = {val} (float={fval})")
            pos += 4
        else:
            out.append(f"{'  '*indent}[{tag_start}] field {field_no} wire_type {wire_type} DESCONHECIDO, abortando")
            raise ValueError("wire type desconhecido")
    return out


def decode_length_prefixed_stream(path, max_records=None):
    with open(path, "rb") as f:
        buf = f.read()
    pos = 0
    rec_no = 0
    records = []
    while pos < len(buf):
        rec_start = pos
        length, pos = read_varint(buf, pos)
        data = buf[pos:pos+length]
        pos += length
        rec_no += 1
        records.append((rec_start, length, data))
        if max_records and rec_no >= max_records:
            break
    return records


if __name__ == "__main__":
    path = sys.argv[1]
    max_records = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    records = decode_length_prefixed_stream(path, max_records=max_records)
    print(f"total registros lidos (limitado a {max_records}): {len(records)}")
    for i, (start, length, data) in enumerate(records):
        print(f"\n=== registro {i} @ offset {start}, len {length} ===")
        try:
            lines = decode_message(data, 0, len(data))
            print("\n".join(lines))
        except Exception as e:
            print(f"ERRO decodificando: {e}")
            print(data.hex())
