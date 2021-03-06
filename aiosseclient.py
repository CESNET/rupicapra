import aiohttp


# taken from https://github.com/ebraminio/aiosseclient/blame/main/aiosseclient.py
async def aiosseclient(url, last_id=None, **kwargs):
    if 'headers' not in kwargs:
        kwargs['headers'] = {}

    # The SSE spec requires making requests with Cache-Control: nocache
    kwargs['headers']['Cache-Control'] = 'no-cache'

    # The 'Accept' header is not required, but explicit > implicit
    kwargs['headers']['Accept'] = 'text/event-stream'

    if last_id:
        kwargs['headers']['Last-Event-ID'] = last_id

    # Override default timeout of 5 minutes
    timeout = aiohttp.ClientTimeout(total=None, connect=None, sock_connect=None, sock_read=None)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        response = await session.get(url, **kwargs)
        lines = []
        async for line in response.content:
            line = line.decode('utf8')

            if line == '\n' or line == '\r' or line == '\r\n':
                yield ''.join(lines)
                lines = []
            elif line.startswith('data: '):
                lines.append(line[len('data: '):])
            else:
                raise RuntimeError('Malformed line: no "data: " prefix or an empty line')
