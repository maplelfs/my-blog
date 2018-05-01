#!/usr/bin/env python
# -*- coding:utf-8 -*-
import asyncio
from app import init



loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()