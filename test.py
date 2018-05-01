#!/usr/bin/python
# coding:utf-8

import orm, asyncio, hashlib
from models import User, Blog, Comment

loop = asyncio.get_event_loop()
async def test():
	await orm.create_pool(loop, user='root', password='maple', db='awesome')
	pass
	u = User(id=1, name='maple', email='1547973055@qq.com',
			 password=hashlib.sha1('1547973055@qq.com:1051210028'.encode('utf-8')).hexdigest(), admin=True, image='about:blank')
	await u.save()
#	await u.remove()


loop.run_until_complete(test())
loop.run_forever()
