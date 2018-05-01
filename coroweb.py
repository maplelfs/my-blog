#!/usr/bin/python
# coding:utf-8

import functools, logging, inspect, asyncio, os
from aiohttp import web
from urllib import parse
from apis import APIError
logging.basicConfig(level=logging.INFO)


# 建立视图函数装饰器，用来存储、附带URL信息
def Handler_decorator(path, *, method):
	def decorator(func):
		@functools.wraps(func)
		def warpper(*args, **kw):
			return func(*args, **kw)
		warpper.__route__ = path
		warpper.__method__ = method
		return warpper
	return decorator
# 偏函数。GET POST 方法的路由装饰器
get = functools.partial(Handler_decorator, method = 'GET')
post = functools.partial(Handler_decorator, method = 'POST')


# 使用inspect模块，检查视图函数的参数
# inspect.Parameter.kind 类型：
# POSITIONAL_OR_KEYWORD    位置或必选参数
# VAR_POSITIONAL           可变参数 *args
# KEYWORD_ONLY             命名关键词参数
# VAR_KEYWORD              可变关键词参数 **kw

# POSITIONAL_ONLY 这类型在官方说明是不会出现在普通函数的,所以我们可以不考虑
# POSITIONAL_ONLY          位置参数

# 获取命名关键词参数
def get_named_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			args.append(name)
	return tuple(args)


# 判断是否含有名叫'request'的参数
def has_request_arg(fn):
	params = inspect.signature(fn).parameters
	found = False
	for name, param in params.items():
		if name == 'request':
			found = True
			continue
	return found

# 定义RequestHandler从视图函数中分析其需要接受的参数，从web.Request中获取必要的参数
# 调用视图函数，然后把结果转换为web.Response对象，符合aiohttp框架要求
class RequestHandler(object):
	def __init__(self, app, fn):
		self._app = app
		self._func = fn
		self._named_kw_args = get_named_kw_args(fn)
		self._has_request_arg = has_request_arg(fn)

	async def __call__(self, request):
		logging.info('!fn:%s'%inspect.signature(self._func))

		kw = None # 定义kw，用于保存request中参数
		if request.method == 'POST':
			# 根据request参数中的content_type使用不同解析方法：
			if request.content_type == None: # 如果content_type不存在，返回400错误
				return web.HTTPBadRequest(text='Missing Content_Type.')
			ct = request.content_type.lower() # 小写，便于检查
			# ct = 'application/x-www-form-urlencoded'
			if ct.startswith('application/json'):  # json格式数据
				params = await request.json() # 仅解析body字段的json数据
				if not isinstance(params, dict): # request.json()返回dict对象
					return web.HTTPBadRequest(text='JSON body must be object.')
				kw = params
			else:
				return web.HTTPBadRequest(text='Unsupported Content-Type: %s' % request.content_type)
		if request.method == 'GET':
			kw = dict()
			qs = request.query_string # 返回URL查询语句，?后的键值。string形式。
			logging.info('!GET, fn:%s, query_string:%s'%(self._func, qs))
			if qs:
				for k, v in parse.parse_qs(qs, True).items(): # 返回查询变量和值的映射，dict对象。True表示不忽略空格。
					kw[k] = v[0]
		copy = dict()
		for name in self._named_kw_args:
			if name in kw:
				copy[name] = kw[name]
		kw = copy

		for k, v in request.match_info.items():
			kw[k] = v

		if self._has_request_arg:
			kw['request'] = request

		logging.info('call with args: %s' % str(kw))
		try:
			r = await self._func(**kw)
			return r
		except APIError as e:
			return dict(error=e.error, data=e.data, message=e.message)



# 编写一个add_route函数，用来注册一个视图函数
def add_route(app, fn):
	method = getattr(fn, '__method__', None)
	path = getattr(fn, '__route__', None)
	if method is None or path is None:
		raise ValueError('@get or @post not defined in %s.' % fn.__name__)
	# 判断URL处理函数是否协程并且是生成器
	if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
		# 将fn转变成协程
		fn = asyncio.coroutine(fn)
	logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ','.join(inspect.signature(fn).parameters.keys())))
	# 注意这里的视图函数是RequestHandler(object).__init__(app,fn)，使用时调用__call__->类函数，当作函数使用
	# 在app中注册经RequestHandler类封装的视图函数
	app.router.add_route(method, path, RequestHandler(app, fn))

# 导入模块，批量注册视图函数
def add_routes(app, module_name):
	mod = __import__(module_name)
	for attr in dir(mod): # dir()迭代出mod模块中所有的类，实例及函数等对象,str形式
		if attr.startswith('_'):
			continue # 忽略'_'开头的对象，直接继续for循环
		fn = getattr(mod, attr)
		# 确保是函数
		if callable(fn):
			# 确保视图函数存在method和path
			method = getattr(fn, '__method__', None)
			path = getattr(fn, '__route__', None)
			if method and path:
				# 注册
				add_route(app, fn)

# 添加静态文件，如image，css，javascript等
def add_static(app):
	# 拼接static文件目录
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
	# path = os.path.join(os.path.abspath('.'), 'static')

	app.router.add_static('/static/', path)
	logging.info('add static %s => %s' % ('/static/', path))
