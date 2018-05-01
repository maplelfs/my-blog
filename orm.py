#!/usr/bin/python
# coding:utf-8

import aiomysql, asyncio, logging
from fields import Field
logging.basicConfig(level=logging.INFO)



# SQL语句反馈
def log(sql, args=()):
	logging.info('SQL: %s, %s' % (sql, args))

# 创建一个全局连接池
async def create_pool(loop, **kw):
	logging.info('create database connection pool...')
	global __pool
	__pool = await aiomysql.create_pool(
		host = kw.get('host', 'localhost'),
		port = kw.get('port', 3306),
		user = kw['user'],
		password = kw['password'],
		db = kw['db'],
		charset = kw.get('charset', 'utf8'),
		# 是否自动提交事务，在增删改数据库文件时，如果为True,不需要再commit来提交事务
		autocommit = kw.get('autocommit', True),
		maxsize = kw.get('maxsize', 10),
		minsize = kw.get('minsize', 1),
		loop = loop)
	pass
# 单独封装select
# select语句，该协程封装的是查询事务，三个参数顺序：sql语句，sql语句中占位符的参数列表，查询数据的数量
async def select(sql, args, size=None):
	log(sql, args)
	# 获取游标，默认游标返回结果为字典,每一项都是字典，这里可指定元组的元素为字典通过aiomysql.DictCursor
	async with __pool.get() as conn:  # 或--> with await __pool as conn:
		# 创建一个DictCursor类指针，!!返回dict形式的结果集!!
		async with conn.cursor(aiomysql.DictCursor) as cur:
			# 调用游标的execute()方法来执行sql语句，execute()接受两个参数：sql语句(可包含占位符)，占位符对应的值，
			# 使用该形式可以避免直接使用字符串拼接出来的sql注入攻击
			# sql语句的占位符为？，mysql里为%s，做替换
			await cur.execute(sql.replace('?', "%s"), args or ())
			if size:
				# size有值就获取对应数量的数据
				rs = await cur.fetchmany(size)
			else:
				rs = await cur.fetchall()
	logging.info('rows returned: %s' % len(rs))
	return rs

# 封装insert，update，delete
# 要执行INSERT、UPDATE、DELETE语句，可以定义一个通用的execute()函数，
# 因为这3种SQL的执行都需要相同的参数，以及返回一个整数表示影响的行数
async def execute(sql, args, autocommit=True):
	log(sql, args)
	with await __pool as conn:
		if not autocommit:
			# 如果不是自动提交事务，需要手动启动
			await conn.begin()
		try:
			async with conn.cursor(aiomysql.DictCursor) as cur:
				await cur.execute(sql.replace('?', "%s"), args)
				# 获取增删改影响的行数
				affected = cur.rowcount
			if not autocommit:
				await conn.commit()
		except BaseException as e:
			if not autocommit:
				# 回滚，在执行commit()之前如果出现错误，就回滚到执行事务前的状态，以免影响数据库的完整性
				await conn.rollback()
			raise e
		return affected


# # 创建占位符，用于insert，update，delete语句
# def create_args_string(num):
# 	return ','.join(['?']*num)

# 定义Metaclass元类
class ModelMetaclass(type):
	def __new__(cls, name, bases, attrs):
		#cls是类，self是实例
		# 排除对Model基类的改动，只作用于Model的子类（数据库表）
		if name == 'Model':
			return type.__new__(cls, name, bases, attrs)
		tableName = attrs.get('__table__', None) or name
		logging.info('found model: %s (table: %s)' % (name, tableName))
		# 保存当前类属性名和Field字段的映射关系
		mappings = dict()
		# 保存除主键外的属性名
		fields = []
		# 主键
		primarykey = None
		for k, v in attrs.items():
			# 找到Field类型字段
			if isinstance(v, Field):
				logging.info('found mapping: %s ==> %s' % (k, v))
				mappings[k] = v
				# 找到主键
				if v.primary_key:
					# 判断主键是否已被赋值
					if primarykey:
						raise BaseException('Duplicate primary key for field: %s' % k)
					primarykey = k
				else:
					#保存非主键的列名
					fields.append(k)
		if not primarykey:
			raise BaseException('primary key not found')
		for k in mappings.keys():
			attrs.pop(k)
		#保存除主键外的属性名为``（输出字符串）的列表形式
		escaped_fields = list(map(lambda f: '`%s`' % f, fields))
		# 映射关系，表名，字段名，主键名
		# 将属性名和Field字段保存到类的__mappings__属性中
		attrs['__mappings__'] = mappings
		attrs['__table__'] = tableName
		attrs['__fields__'] = fields
		attrs['__primary_key__'] = primarykey
		# 构造默认的select，insert，update，delete语句，其中添加的反引号``,是为了避免与sql关键字冲突的,否则sql语句会执行出错
		# -------------------eg：select id from user;
		attrs['__select__'] = 'select `%s`, %s from `%s`' % (primarykey, ','.join(escaped_fields), tableName)
		# ------------------eg：insert into user(id,name)values(1,Michael);
		attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ','.join(escaped_fields), primarykey, ','.join(['?']*(len(escaped_fields)+1)))
		# ------------------eg:update user set id=1 where name='Michael';
		attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ','.join(map(lambda f:'`%s`=?' % f, fields)), primarykey)
		# ------------------eg:delete from user where name='Michael';
		attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primarykey)
		return type.__new__(cls, name, bases, attrs)
# 这是模型的基类，继承于dict
class Model(dict, metaclass = ModelMetaclass):
	def __init__(self, **kw):
		# super的另一种写法
		super(Model, self).__init__(self, **kw)
	
	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError('Model object has no attribute: %s' % key)

	def __setattr__(self, key, value):
		self[key] = value

	def getValue(self, key):
		# 继承父类dict的内建函数getattr()
		return getattr(self, key, None)

	def getValueOrDefault(self, key):
		value = getattr(self, key, None)
		if not value:
			field = self.__mappings__[key]
			if field.default is not None:
				#default值可以设置为值或调用对象（无法设置值时，如default = time.time 插入当前时间）
				value = field.default() if callable(field.default) else field.default
				logging.debug('use default value for %s: %s' % (key, str(value)))
		return value

	# 类方法有类变量cls传入，从而可以用cls做一些相关的处理。
	# 有子类继承时，调用该类方法时，传入的类变量cls是子类，而非父类。 
	@classmethod# 新语法，该装饰器用于把类里面定义的方法声明为该类的类方法
	async def findAll(cls, where=None, args=None, **kw):
		if not args:
			args = []
		# 有子类方法继承时,调用此类方法,传入的类变量cls是子类,而非父类
		sql = [cls.__select__] 
		if where: 
			sql.append('where')
			sql.append(where)
		orderBy = kw.get('orderBy', None)
		if orderBy:
			sql.append('order by')
			sql.append(orderBy)
		limit = kw.get('limit', None)
		if limit:
			sql.append('limit')
			if isinstance(limit, int):
				sql.append('?')
				args.append(limit)
			elif isinstance(limit, tuple) and len(limit)==2:
				sql.append('?, ?')
				args.extend(limit)
			else:
				raise('Invalid limit value: %s' % str(limit))
		rs = await select(' '.join(sql), args)	
		# 将返回的结果迭代生成类的实例，返回的都是实例对象, 而非仅仅是数据
		return [cls(**r) for r in rs]

	# 根据主键查找数据库
	@classmethod
	async def find(cls,primarykey):
		sql = '%s where `%s`=?' % (cls.__select__, cls.__primary_key__)
		rs = await select(sql, [primarykey], 1)
		if len(rs) == 0:
			return None
		return cls(**rs[0])

	@classmethod
	async def findNumber(cls, selectField, where=None, args=None):
		# 使用了SQL的聚集函数 count()
		# select %s as __num__ from table ==> __num__表示列的别名，筛选结果列名会变成__num__
		sql = ['select %s __num__ from `%s`' % (selectField, cls.__table__)]
		if where:
			sql.append('where')
			sql.append(where)
		rs = await select(' '.join(sql), args, 1)
		pass
		if len(rs) == 0:
			return None
		# fetchmany()返回列表结果，用索引取出。又因为Dictcursor，值用key取出。
		return rs[0]['__num__']

	# 以下都是对象方法，所以可以不用传参数，方法内部可以使用该对象的所有属性
	# 保存实例到数据库
	async def save(self):
		args = list(map(self.getValueOrDefault, self.__fields__))
		primarykey = self.getValueOrDefault(self.__primary_key__)
		args.append(primarykey)
		rows = await execute(self.__insert__, args)
		if rows != 1:
			logging.warn('failed to insert record: affected rows: %s' % rows)

	# 更新数据库资料
	async def update(self):
		args = list(map(self.getValue, self.__fields__))
		primarykey = self.getValue(self.__primary_key__)
		args.append(primarykey)
		rows = await execute(self.__update__, args)
		if rows != 1:
			logging.warn('failed to update record: affected rows: %s' % rows)

	# 删除数据
	async def remove(self):
		args = [self.getValue(self.__primary_key__)]
		rows = await execute(self.__delete__, args)
		if rows != 1:
			logging.warn('failed to remove by primary key: affected rows: %s' % rows) 




















