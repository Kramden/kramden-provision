desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils, args: ['kramden-provision-osload.desktop', 'kramden-provision-finaltest.desktop', 'kramden-device.desktop'])
endif

install_data('kramden-provision-osload.desktop',
  install_dir: join_paths(get_option('datadir'), 'applications'),
)
install_data('kramden-provision-finaltest.desktop',
  install_dir: join_paths(get_option('datadir'), 'applications'),
)
install_data('kramden-device.desktop',
  install_dir: join_paths(get_option('datadir'), 'applications'),
)

subdir('icons')
