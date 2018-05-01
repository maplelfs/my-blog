#!/usr/bin/python
# coding:utf-8

# 定义Field基类，负责保存db表的字段名和字段类型

class Field(object):
    def __init__(self, ddl, primary_key, default):
        self.ddl = ddl
        self.primary_key = primary_key
        self.default = default
        L=[]

    def __str__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.ddl)
class StringField(Field):
    def __init__(self, ddl='varchar(255)', primary_key=False, default=None):
        super(StringField, self).__init__(ddl, primary_key, default)
class IntegerField(Field):
    def __init__(self, ddl='bigint', primary_key=False, default=0):
        super(IntegerField, self).__init__(ddl, primary_key, default)
class BooleanField(Field):
    def __init__(self, ddl='Boolean', primary_key=False, default=False):
        super(BooleanField, self).__init__(ddl, primary_key, default)
class TextField(Field):
    def __init__(self, ddl='Text', primary_key=False, default=None):
        super(TextField, self).__init__(ddl, primary_key, default)
class FloatField(Field):
    def __init__(self, ddl='real', primary_key=False, default=None):
        super(FloatField, self).__init__(ddl, primary_key, default)	