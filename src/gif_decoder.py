# Minimal GIF decoder for MicroPython.
# Streams frames into a provided RGB565 framebuffer.


def _read_exact(handle, size):
    data = handle.read(size)
    if data is None or len(data) != size:
        raise ValueError("Unexpected EOF")
    return data


def _read_u16_le(handle):
    data = _read_exact(handle, 2)
    return data[0] | (data[1] << 8)


def _read_sub_blocks(handle):
    chunks = bytearray()
    while True:
        size = _read_exact(handle, 1)[0]
        if size == 0:
            break
        chunks.extend(_read_exact(handle, size))
    return bytes(chunks)


def _write_rgb565(out_buf, pos, palette, idx):
    base = idx * 3
    r = palette[base]
    g = palette[base + 1]
    b = palette[base + 2]
    color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    out_buf[pos] = (color >> 8) & 0xFF
    out_buf[pos + 1] = color & 0xFF


def _lzw_decode_to_rgb565_stream(
    handle,
    min_code_size,
    expected_pixels,
    palette,
    out_buf,
    transparent_index,
    img_x,
    img_y,
    img_w,
    img_h,
    screen_w,
):
    clear_code = 1 << min_code_size
    end_code = clear_code + 1
    code_size = min_code_size + 1
    next_code = end_code + 1

    prefix = [0] * 4096
    suffix = bytearray(4096)
    stack = bytearray(4096)

    def reset_dict():
        nonlocal code_size, next_code
        for i in range(clear_code):
            prefix[i] = 0
            suffix[i] = i
        code_size = min_code_size + 1
        next_code = end_code + 1

    reset_dict()

    bit_buf = 0
    bit_count = 0
    prev_code = None
    out_pos = 0
    cur_x = 0
    cur_y = 0

    def write_code(code):
        nonlocal out_pos, cur_x, cur_y
        top = 0
        while code >= clear_code:
            stack[top] = suffix[code]
            top += 1
            code = prefix[code]
        stack[top] = code
        top += 1
        while top:
            top -= 1
            idx = stack[top]
            if out_pos >= expected_pixels:
                return False
            if transparent_index is None or idx != transparent_index:
                dst = ((img_y + cur_y) * screen_w + (img_x + cur_x)) * 2
                _write_rgb565(out_buf, dst, palette, idx)
            out_pos += 1
            cur_x += 1
            if cur_x >= img_w:
                cur_x = 0
                cur_y += 1
        return True

    block_size = _read_exact(handle, 1)[0]
    block_bytes = _read_exact(handle, block_size) if block_size else b""
    block_pos = 0

    def read_byte():
        nonlocal block_size, block_bytes, block_pos
        while True:
            if block_size == 0:
                return None
            if block_pos < block_size:
                value = block_bytes[block_pos]
                block_pos += 1
                return value
            block_size = _read_exact(handle, 1)[0]
            if block_size == 0:
                return None
            block_bytes = _read_exact(handle, block_size)
            block_pos = 0

    def drain_sub_blocks():
        nonlocal block_size, block_bytes, block_pos
        if block_size and block_pos < block_size:
            _read_exact(handle, block_size - block_pos)
        while True:
            size = _read_exact(handle, 1)[0]
            if size == 0:
                break
            _read_exact(handle, size)

    def read_code():
        nonlocal bit_buf, bit_count
        while bit_count < code_size:
            next_byte = read_byte()
            if next_byte is None:
                return None
            bit_buf |= next_byte << bit_count
            bit_count += 8
        value = bit_buf & ((1 << code_size) - 1)
        bit_buf >>= code_size
        bit_count -= code_size
        return value

    while True:
        code = read_code()
        if code is None:
            break
        if code == clear_code:
            reset_dict()
            prev_code = None
            continue
        if code == end_code:
            break

        if code < next_code:
            if not write_code(code):
                break
            first = suffix[code] if code >= clear_code else code
        elif prev_code is not None:
            if not write_code(prev_code):
                break
            first = suffix[prev_code] if prev_code >= clear_code else prev_code
            if out_pos >= expected_pixels:
                break
            if transparent_index is None or first != transparent_index:
                dst = ((img_y + cur_y) * screen_w + (img_x + cur_x)) * 2
                _write_rgb565(out_buf, dst, palette, first)
            out_pos += 1
            cur_x += 1
            if cur_x >= img_w:
                cur_x = 0
                cur_y += 1
        else:
            break

        if prev_code is not None and next_code < 4096:
            prefix[next_code] = prev_code
            suffix[next_code] = first
            next_code += 1
            if next_code >= (1 << code_size) and code_size < 12:
                code_size += 1

        prev_code = code

    drain_sub_blocks()
    return


class GifDecoder:
    def __init__(self, path):
        self.path = path

    def decode_into(self, out_buf, width, height):
        with open(self.path, "rb") as handle:
            header = _read_exact(handle, 6)
            if header not in (b"GIF87a", b"GIF89a"):
                raise ValueError("Not a GIF file")

            screen_w = _read_u16_le(handle)
            screen_h = _read_u16_le(handle)
            packed = _read_exact(handle, 1)[0]
            bg_index = _read_exact(handle, 1)[0]
            _read_exact(handle, 1)

            if screen_w != width or screen_h != height:
                raise ValueError(
                    "GIF size must match LCD size ({}x{}), got {}x{}".format(
                        width, height, screen_w, screen_h
                    )
                )

            has_global_ct = (packed & 0x80) != 0
            global_ct_size = 2 ** ((packed & 0x07) + 1) if has_global_ct else 0

            global_palette = b""
            if has_global_ct:
                global_palette = _read_exact(handle, global_ct_size * 3)

            delay_ms = 100
            transparent_index = None
            gce_seen = False

            while True:
                block = handle.read(1)
                if not block:
                    break
                block_id = block[0]

                if block_id == 0x3B:
                    break

                if block_id == 0x21:
                    label = _read_exact(handle, 1)[0]
                    if label == 0xF9:
                        _read_exact(handle, 1)
                        packed_fields = _read_exact(handle, 1)[0]
                        delay = _read_u16_le(handle)
                        transparent = _read_exact(handle, 1)[0]
                        _read_exact(handle, 1)

                        delay_ms = delay * 10 if delay > 0 else 100
                        transparent_index = (
                            transparent if (packed_fields & 0x01) else None
                        )
                        gce_seen = True
                    else:
                        _read_sub_blocks(handle)
                    continue

                if block_id != 0x2C:
                    break

                img_x = _read_u16_le(handle)
                img_y = _read_u16_le(handle)
                img_w = _read_u16_le(handle)
                img_h = _read_u16_le(handle)
                packed_fields = _read_exact(handle, 1)[0]

                has_local_ct = (packed_fields & 0x80) != 0
                interlaced = (packed_fields & 0x40) != 0
                local_ct_size = 2 ** ((packed_fields & 0x07) + 1) if has_local_ct else 0

                if interlaced:
                    raise ValueError("Interlaced GIFs are not supported")

                if not gce_seen:
                    delay_ms = 100
                    transparent_index = None

                palette = global_palette
                if has_local_ct:
                    palette = _read_exact(handle, local_ct_size * 3)

                lzw_min = _read_exact(handle, 1)[0]

                expected = img_w * img_h
                _lzw_decode_to_rgb565_stream(
                    handle,
                    lzw_min,
                    expected,
                    palette,
                    out_buf,
                    transparent_index,
                    img_x,
                    img_y,
                    img_w,
                    img_h,
                    screen_w,
                )
                yield delay_ms

                gce_seen = False

            return
