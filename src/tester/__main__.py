import argparse

if __name__ == '__main__':
	from .tester import test, save

	parser = argparse.ArgumentParser()
	sub = parser.add_subparsers(dest="instruction")

	sread = sub.add_parser("test")
	sread.add_argument('-s', '--source', required=True)

	swrite = sub.add_parser("save")
	swrite.add_argument('-o', '--output', required=True)
	swrite.add_argument('-a', '--args', required=True, nargs='*')
	swrite.add_argument('--stdin', default=None)

	args = parser.parse_args()

	if args.instruction == 'test':
		test(args.source)

	if args.instruction == 'save':
		save(args.output, args.args, args.stdin)
