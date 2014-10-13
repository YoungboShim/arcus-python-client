#
# arcus-python-client - Arcus python client drvier
# Copyright 2014 NAVER Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
 

import telnetlib
import socket

from kazoo.client import KazooClient
import kazoo
from kazoo.exceptions import *


class arcus_cache:
	def __init__(self, zk_addr, code):
		self.code = code
		self.zk_addr = zk_addr
		self.node = []
		self.active_node = []
		self.dead_node = []

	def __repr__(self):
		repr = '[Service Code: %s] (zk:%s)\n (node) %s\n (active) %s\n (dead) %s' % (self.code, self.zk_addr, self.node, self.active_node, self.dead_node)
		return repr


class arcus_node:
	def __init__(self, ip, port):
		self.ip = ip
		self.port = port 

		self.name = ''
		self.code = ''
		self.zk_addr = ''
		self.active = False

	def __repr__(self):
		if self.name and self.code:
			return '[%s:%s-(%s,%s)]' % (self.ip, self.port, self.name, self.code)
		elif self.name:
			return '[%s:%s-(%s)]' % (self.ip, self.port, self.name)
		elif self.code:
			return '[%s:%s-(%s)]' % (self.ip, self.port, self.code)

		return '[%s:%s]' % (self.ip, self.port)

	def do_arcus_command(self, command):
		tn = telnetlib.Telnet(self.ip, self.port)
		tn.write(bytes(command + '\n', 'utf-8'))

		if command[0:5] == 'scrub' or command[0:5] == 'flush':
			result = tn.read_until(bytes('OK', 'utf-8'))
		else:
			result = tn.read_until(bytes('END', 'utf-8'))


		result = result.decode('utf-8');
		tn.write(bytes('quit\n', 'utf-8'))
		tn.close()
		return result;


class zookeeper:
	def __init__(self, address):
		self.address = address
		self.zk = KazooClient(address)
		self.zk.start()

		self.arcus_cache_map = {} 
		self.arcus_node_map = {}

		self.force = False

	def __repr__(self):
		repr = '[ZooKeeper: %s]' % (self.address)

		for code, cache in self.arcus_cache_map.items():
			repr = '%s\n\n%s' % (repr, cache)

		return repr

	def set_force(self):
		self.force = True

	def zk_read(self, path):
		data, stat = self.zk.get(path)
		children = self.zk.get_children(path)
		return data, stat, children
	
	def zk_exists(self, path):
		if self.zk.exists(path) == None:
			return False

		return True

	def zk_create(self, path, value):
		try:
			self.zk.create(path, bytes(value, 'utf-8'))
		except NodeExistsError:
			if self.force == False:
				raise NodeExistsError
		
	def zk_delete(self, path):
		try:
			self.zk.delete(path)
		except NoNodeError:
			if self.force == False:
				raise NoNodeError
		
	def zk_delete_tree(self, path):
		try:
			self.zk.delete(path, recursive=True)
		except NoNodeError:
			if self.force == False:
				raise NoNodeError

	def zk_update(self, path, value):
		try:
			self.zk.set(path, bytes(value, 'utf-8'))
		except NoNodeError:
			if self.force == False:
				raise NoNodeError

	def get_arcus_cache_list(self):
		children = self.zk.get_children('/arcus/cache_list/')
		return children

	def get_arcus_node_of_code(self, code, server):
		children = self.zk.get_children('/arcus/cache_list/' + code)

		ret = []
		for child in children:
			addr, name = child.split('-')
			ip, port = addr.split(':')

			if server != '' and (server != ip and server != name):
				continue # skip this

			node = arcus_node(ip, port)
			node.name = name;
			ret.append(node)

		return ret

	def get_arcus_node_of_server(self, addr):
		ip = socket.gethostbyname(addr)
		children = self.zk.get_children('/arcus/cache_server_mapping/')

		ret = []
		for child in children:
			l = len(ip)
			if child[:l] == ip:
				code = self.zk.get_children('/arcus/cache_server_mapping/' + child)
				try:
					ip, port = child.split(':')
				except ValueError:
					print('cache_server_mapping ValueError: %s' % child)
					ip = child
					port = '0'

				node = arcus_node(ip, port)
				node.code = code[0]
				ret.append(node)
		return ret

	def get_arcus_node_all(self):
		children = self.zk.get_children('/arcus/cache_server_mapping/')

		ret = []
		for child in children:
			code = self.zk.get_children('/arcus/cache_server_mapping/' + child)

			try:
				ip, port = child.split(':')
			except ValueError:
				print('cache_server_mapping ValueError: %s' % child)
				ip = child
				port = '0'

			node = arcus_node(ip, port)
			node.code = code[0]
			ret.append(node)

		return ret

	def load_all(self):
		codes = self.get_arcus_cache_list()
		for code in codes:
			cache = arcus_cache(self.address, code)
			self.arcus_cache_map[code] = cache;

		nodes = self.get_arcus_node_all()

		for node in nodes:
			self.arcus_node_map[node.ip + ":" + node.port] = node;
			self.arcus_cache_map[node.code].node.append(node)

		for code, cache in self.arcus_cache_map.items():
			children = self.zk.get_children('/arcus/cache_list/' + code)

			for child in children:
				addr, name = child.split('-')
				try:
					node = self.arcus_node_map[addr]
				except KeyError:
					print('[%s] active node KeyError: %s' % (code, addr))
						
			
				node.active = True
				cache.active_node.append(node)
			
			for node in cache.node:
				if node.active == False:
					cache.dead_node.append(node)

			

		
		




