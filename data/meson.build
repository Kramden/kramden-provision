desktop_files = ['kramden-provision-osload.desktop', 'kramden-provision-finaltest.desktop', 'kramden-device.desktop']

# Desktop files
osload_file = configure_file(
  input: 'kramden-provision-osload.desktop.in',
  output: 'kramden-provision-osload.desktop',
  copy: true,
  install: true,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

finaltest_file = configure_file(
  input: 'kramden-provision-finaltest.desktop.in',
  output: 'kramden-provision-finaltest.desktop',
  copy: true,
  install: true,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

device_file = configure_file(
  input: 'kramden-device.desktop.in',
  output: 'kramden-device.desktop',
  copy: true,
  install: true,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils, args: desktop_files)
endif

subdir('icons')
