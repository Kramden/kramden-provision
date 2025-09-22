desktop_files = ['kramden-provision-osload.desktop', 'kramden-provision-finaltest.desktop', 'kramden-device.desktop', 'kramden-spec.desktop']

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

spec_file = configure_file(
  input: 'kramden-spec.desktop.in',
  output: 'kramden-spec.desktop',
  copy: true,
  install: true,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

spec_autoinstall_file = configure_file(
  input: 'kramden-spec.desktop.in',
  output: 'kramden-spec.desktop',
  copy: true,
  install: true,
  install_dir: join_paths(get_option('sysconfdir'), 'xdg/autostart')
)

device_file = configure_file(
  input: 'kramden-device.desktop.in',
  output: 'kramden-device.desktop',
  copy: true,
  install: true,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

device_autoinstall_file = configure_file(
  input: 'kramden-device.desktop.in',
  output: 'kramden-device.desktop',
  copy: true,
  install: true,
  install_dir: join_paths(get_option('sysconfdir'), 'xdg/autostart')
)

subdir('icons')
subdir('documents')
