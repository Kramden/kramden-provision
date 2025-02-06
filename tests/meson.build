python3 = import('python').find_installation()

sources = [
  'test_utils.py',
]

test('unittests', python3, args : ['-m', 'unittest', 'discover', '-s', '.'])
