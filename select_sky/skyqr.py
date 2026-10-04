"""QR Code encoder for the locate screen: byte mode, error correction L, versions 1 to 7, mask 7.

matrix(text) -> (size, rows). rows[y] is row y as bytes, one bit a module: the leftmost module is
the top bit of the first byte and 1 is dark. Version 7 holds 154 bytes, which covers a short URL.

One fixed mask keeps the encoder small and quick. Every reader takes the mask from the format bits,
and the standard's penalty search only steers away from patterns that confuse readers. Mask 7 scores
lowest on average for a URL and a random code, close to what the search picks.
"""

# Data codewords, error-correction codewords per block, and blocks, for versions 1 to 7.
_V = ((19, 7, 1), (34, 10, 1), (55, 15, 1), (80, 20, 1), (108, 26, 1), (136, 18, 2), (156, 20, 2))
_FORMAT = 0x6976        # level L, mask 7, with its BCH check bits and the standard's XOR
_VERSION = 0x07C94      # version 7, with its BCH check bits


def _mul(x, y):
    """x times y in GF(256), reduced by x^8 + x^4 + x^3 + x^2 + 1. Bitwise, so no tables sit in memory."""
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _codewords(t, data, e, blocks):
    """Data codewords for the bytes t, with each block's Reed-Solomon check bytes, interleaved."""
    n = len(t)
    d = bytearray(data)
    d[0] = 0x40 | n >> 4                    # byte mode, then the length, then the bytes, 4 bits late
    low = n & 15
    for i in range(n):
        d[i + 1] = low << 4 | t[i] >> 4
        low = t[i] & 15
    d[n + 1] = low << 4                     # the terminator is the last 4 bits
    for i in range(n + 2, data):
        d[i] = 0x11 if (i - n) & 1 else 0xEC
    div = bytearray(e + 1)                  # generator polynomial without its leading 1; div[e] stays 0
    div[e - 1] = 1
    r = 1
    for _ in range(e):
        for j in range(e):
            div[j] = _mul(div[j], r) ^ div[j + 1]
        r = _mul(r, 2)
    k = data // blocks
    cw = bytearray(data + e * blocks + 1)   # one spare byte of zeros: the filler bits after the last codeword
    for j in range(blocks):
        rem = bytearray(e)
        for i in range(k):
            b = d[j * k + i]
            cw[i * blocks + j] = b
            f = b ^ rem[0]
            for q in range(e - 1):
                rem[q] = rem[q + 1] ^ _mul(div[q], f)
            rem[e - 1] = _mul(div[e - 1], f)
        for i in range(e):
            cw[data + i * blocks + j] = rem[i]
    return cw


def matrix(text):
    """The QR code for text as (size, rows). Raises ValueError when text is over 154 bytes."""
    t = text.encode()
    v = 1
    while v < 7 and len(t) > _V[v - 1][0] - 2:
        v += 1
    data, e, blocks = _V[v - 1]
    if len(t) > data - 2:
        raise ValueError("text too long")
    cw = _codewords(t, data, e, blocks)
    size = 4 * v + 17
    m = bytearray(size * size)              # per module: bit 0 dark, bit 1 part of a fixed pattern

    def put(x, y, dark):
        m[y * size + x] = 2 | dark

    for i in range(size):
        put(6, i, i % 2 == 0)               # timing
        put(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
        for dy in range(-4, 5):             # finder and the light strip around it
            for dx in range(-4, 5):
                if 0 <= cx + dx < size and 0 <= cy + dy < size:
                    put(cx + dx, cy + dy, max(abs(dx), abs(dy)) not in (2, 4))
    far = 4 * v + 10
    pos = (6, 22, 38) if v == 7 else (6, far) if v > 1 else ()
    for cx in pos:
        for cy in pos:
            if (cx, cy) not in ((6, 6), (6, far), (far, 6)):    # those would sit on a finder
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        put(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
    for i in range(15):                     # format bits, twice
        b = _FORMAT >> i & 1
        if i < 8:
            put(8, i + (i > 5), b)
            put(size - 1 - i, 8, b)
        else:
            put(14 - i + (i < 9), 8, b)
            put(8, size - 15 + i, b)
    put(8, size - 8, 1)                     # the one dark module
    if v == 7:
        for i in range(18):                 # version bits, twice
            b = _VERSION >> i & 1
            put(size - 11 + i % 3, i // 3, b)
            put(i // 3, size - 11 + i % 3, b)

    i = 0
    for right in range(size - 1, 0, -2):    # two columns at a time, up and down in turn, skipping the timing column
        right -= right < 7
        for k in range(size):
            y = size - 1 - k if (right + 1) & 2 == 0 else k
            for x in (right, right - 1):
                if not m[y * size + x] & 2:
                    m[y * size + x] = (cw[i >> 3] >> (7 - (i & 7)) & 1) ^ ((((x + y) & 1) + x * y % 3 + 1) & 1)   # mask 7
                    i += 1

    rows = []
    for y in range(size):
        r = bytearray((size + 7) // 8)
        for x in range(size):
            if m[y * size + x] & 1:
                r[x >> 3] |= 0x80 >> (x & 7)
        rows.append(r)
    return size, rows
