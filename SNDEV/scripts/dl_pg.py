import urllib.request, os
url = "https://get.enterprisedb.com/postgresql/postgresql-15.7-1-windows-x64-binaries.zip"
out = os.path.join(os.environ['TEMP'], 'pg15.zip')
req = urllib.request.Request(url)
start = os.path.getsize(out) if os.path.exists(out) else 0
if start:
    req.add_header('Range', 'bytes=%d-' % start)
    print("Resuming from", start)
r = urllib.request.urlopen(req, timeout=300)
mode = 'ab' if start else 'wb'
total = start
with open(out, mode) as f:
    while True:
        b = r.read(1 << 20)
        if not b:
            break
        f.write(b)
        total += len(b)
        if total % (20 * 1024 * 1024) < (1 << 20):
            print("Downloaded", total, "bytes")
print("DONE size", os.path.getsize(out))
