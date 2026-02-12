moduledir = join_paths(pkgdatadir, 'kramden_provision')
gnome = import('gnome')

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'kramden-provision-osload.in',
  output: 'kramden-provision-osload',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

configure_file(
  input: 'kramden-provision-finaltest.in',
  output: 'kramden-provision-finaltest',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

configure_file(
  input: 'kramden-spec.in',
  output: 'kramden-spec',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

configure_file(
  input: 'kramden-device.in',
  output: 'kramden-device',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

configure_file(
  input: 'kramden-provision-secureerase.in',
  output: 'kramden-provision-secureerase',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

sources = [
  'check_packages.py',
  'constants.py',
  'deviceinfo.py',
  'finaltestcomplete.py',
  'finaltest.py',
  'generate_tracking_sheet.py',
  'knum.py',
  'landscape.py',
  'manualtest.py',
  'observable.py',
  'osloadcomplete.py',
  'osload.py',
  'sortly.py',
  'sortly_register.py',
  'sortly_lookup_by_name.py',
  'sortly_lookup_by_serial.py',
  'sortly_register.py',
  'sortly_update_system_info.py',
  'spec.py',
  'speccomplete.py',
  'specinfo.py',
  'sysinfo.py',
  'secureerase.py',
  'utils.py',
  'getlearngive.png',
  'landscape_dark.png',
  'guide.py',
]

install_emptydir(moduledir / 'css')
install_data('css/style.css',install_dir: join_paths(moduledir,'css'))
install_data(sources, install_dir: moduledir)
