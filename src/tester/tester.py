from pynary import IOobject, IOStream, types, cast_object
from io import BytesIO
from dataclasses import dataclass, field
from typing import TypeAlias, BinaryIO
from pathlib import Path
import subprocess

@IOobject
class Blob(IOStream):
	size: types.INT_BE
	text: types.BYTES_BE

	@classmethod
	def new(cls, *, text: str) -> 'Blob':
		return cast_object(Blob, {'size': len(text), 'text': text.encode('utf8')})

	@classmethod
	def to(cls, b: 'Blob') -> str:
		return b[1] # pyright: ignore

	def read(self):
		return self.size, self.text

	def write(self, text: bytes):
		self.size = types.INT_BE(len(text))
		self.text = types.BYTES_BE(text)

@IOobject
class SBlob(IOStream):
	size: types.INT_BE
	text: types.STR_BE

	@classmethod
	def new(cls, *, text: str) -> 'SBlob':
		return cast_object(SBlob, {'size': len(text), 'text': text.encode('utf8')})

	@classmethod
	def to(cls, b: 'SBlob') -> str:
		return b[1] # pyright: ignore

	def read(self):
		return self.size, self.text

	def write(self, text: str):
		self.size = types.INT_BE(len(text))
		self.text = types.STR_BE(text.encode('utf8'))

@IOobject
class Integer(IOStream):
	N: types.INT_BE

	@classmethod
	def new(cls, n, **kwargs) -> 'Integer':
		return cast_object(Integer, {'N': n})

	def read(self):
		return self.N

	def write(self, n):
		self.N = types.INT_BE(n)

@IOobject
class Field(IOStream):
	start: types.CHAR_BE
	case: types.CHAR_BE
	space: types.CHAR_BE
	key: SBlob

	def read(self):
		start = self.start
		case = self.case
		space = self.space
		key = self.key
		return case, SBlob.to(key)

	def write(self, case: str, key):
		self.start = types.CHAR_BE(b':')
		self.case = types.CHAR_BE(case[0].encode('utf8'))
		self.space = types.CHAR_BE(b' ')
		self.key = SBlob.new(text=key)

ParamValue: TypeAlias = int | str | bytes | list[str] | None

@dataclass
class parameter:
	type: str
	key: str
	value: ParamValue

@dataclass
class structure:
	parameters: list[parameter] = field(default_factory=list)
	args: list[str] = field(default_factory=list)

	def __getitem__(self, key):
		for p in self.parameters:
			if p.key == key:
				return p
		raise IndexError

	def add_parameter(self, type: str, key: str, value: ParamValue):
		self.parameters.append(parameter(type, key, value))
		return self
		
	@classmethod
	def read(cls, io):
		self = cls()
		while True:
			f = Field(io)
			case, key = f.read()
			if case == 'i':
				self.parameters.append(parameter(str(case), key, int(Integer(io).read())))
			elif case == 'b':
				self.parameters.append(parameter(str(case), key, Blob(io).read()[1]))
			elif case == 'B':
				self.parameters.append(parameter(str(case), key, str(SBlob(io).read()[1])))
			elif case == 'l':
				nargs = Integer(io).read()
				self.parameters.append(parameter(str(case), key,
					 [str(SBlob(io).read()[1]) for i in range(nargs)]
				))
			elif case == 'E':
				break
		return self

	def write(self, io):
		for p in self.parameters:
			Field(io).write(p.type, p.key)
			if p.type == 'i':
				assert isinstance(p.value, int)
				Integer(io).write(p.value)
			if p.type == 'b':
				assert isinstance(p.value, bytes)
				Blob(io).write(p.value)
			if p.type == 'B':
				assert isinstance(p.value, str)
				SBlob(io).write(p.value)
			if p.type == 'l':
				assert isinstance(p.value, list)
				Integer(io).write(len(p.value))
				for s in p.value:
					assert isinstance(s, str)
					SBlob(io).write(s)
		Field(io).write("E", '\0')
		

def cmd(cmd: list[str]):
	print('[RUN]', cmd)
	return subprocess.Popen(cmd,
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			shell=True,
		)

def test(path: str) -> tuple[int, int, bytes, bytes, bool]:
	with open(path, 'rb') as f:
		s = structure.read(f)
		ret, halted, argv, in_, out, err = run(s['argv'].value, s['stdin'].value) # pyright: ignore

		failure = 0
		if ret != s['ret'].value:
			print(f"\033[31mRETURNCODE\033[0m {ret} != {s['ret'].value}")
			failure = 1
		if halted != s['halted'].value:
			print(f"\033[31mHALTED\033[0m {halted} != {s['halted'].value}")
			failure = 1
		if out != s['stdout'].value:
			print(f"\033[31mSTDOUT\033[0m ({out.decode('utf8')}) != ({s['stdout'].value.decode('utf8')})") # pyright: ignore

			failure = 1
		if err != s['stderr'].value:
			print(f"\033[31mSTDOUT\033[0m ({err.decode('utf8')}) != ({s['stderr'].value.decode('utf8')})") # pyright: ignore
			failure = 1
		if not failure:
			print("\033[32mSUCCESS\033[0m")

		return ret, halted, out, err, bool(failure)

def run(args: list[str], stdin: bytes) -> tuple[int, int, list[str], bytes, bytes, bytes]:
	process = cmd(args)
	out, err = process.communicate(input=stdin)

	if process.returncode is None:
		process.kill()
		halted = 1
		ret = 0
	else:
		ret = process.returncode
		halted = 0

	return process.returncode, halted, args, stdin, out, err

def save(output: str | Path | BinaryIO, args: list[str], stdin: str | Path | bytes | BinaryIO) -> tuple[int, int, bytes, bytes]:
	if stdin:
		if isinstance(stdin, (str, Path)):
			with open(stdin, 'rb') as f:
				in_ = f.read()
		elif isinstance(stdin, (bytes,)):
			in_ = stdin
		elif isinstance(stdin, BinaryIO):
			in_ = stdin.read()
		else:
			raise TypeError
	else:
		in_ = b''
	ret, halted, argv, in_, out, err = run(args, in_)

	buffer = BytesIO()
	s = (structure()
		.add_parameter('i', 'ret', ret)
		.add_parameter('i', 'halted', halted)
		.add_parameter('l', 'argv', args)
		.add_parameter('b', 'stdin', in_)
		.add_parameter('b', 'stdout', out)
		.add_parameter('b', 'stderr', err)
	).write(buffer)
	buffer.seek(0)
	if isinstance(output, (str, Path)):
		with open(output, 'wb') as f:
			f.write(buffer.read())
	elif isinstance(output, BinaryIO):
		output.write(buffer.read())
	return ret, halted, out, err
