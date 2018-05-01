import asyncio

from aiohttp import web

async def index(request):
    await asyncio.sleep(0.5)
    # return web.Response(body=b'<h1>Index</h1>',content_type = 'text/html')
    return web.HTTPBadRequest(text='JSON body must be object.')

async def hello(request):
    await asyncio.sleep(0.5)
    text = '<h1>hello, %s!</h1>' % request.match_info['name']
    print(request)
    return web.Response(body=text.encode('utf-8'),content_type = 'text/html')

async def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/', index)
    app.router.add_route('GET', '/{name}', hello)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 7000)
    print('Server started at http://127.0.0.1:7000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()


