import aiohttp


# taken from https://github.com/ebraminio/aiosseclient/blame/main/aiosseclient.py
async def aiosseclient(url, last_id=None, timeout=None, **kwargs):
    if 'headers' not in kwargs:
        kwargs['headers'] = {}

    # The SSE spec requires making requests with Cache-Control: nocache
    kwargs['headers']['Cache-Control'] = 'no-cache'

    # The 'Accept' header is not required, but explicit > implicit
    kwargs['headers']['Accept'] = 'text/event-stream'

    if last_id:
        kwargs['headers']['Last-Event-ID'] = last_id

    if timeout is None:
        # Override default timeout of 5 minutes
        timeout = aiohttp.ClientTimeout(total=None, connect=None, sock_connect=None, sock_read=None)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        response = await session.get(url, **kwargs)
        lines = []
        async for line in response.content:
            line = line.decode('utf8')

            if line.startswith(':'):
                # comment as defined by https://html.spec.whatwg.org/multipage/server-sent-events.html#parsing-an-event-stream
                continue
            elif line == '\n' or line == '\r' or line == '\r\n':
                if len(lines):
                    yield ''.join(lines)
                lines = []
            elif line.startswith('data: '):
                lines.append(line[len('data: '):])
            else:
                raise RuntimeError('Malformed line: no "data: " prefix or an empty line')
