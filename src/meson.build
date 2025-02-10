pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
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
  input: 'kramden-device.in',
  output: 'kramden-device',
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
  'knum.py',
  'landscape.py',
  'manualtest.py',
  'observable.py',
  'osloadcomplete.py',
  'osload.py',
  'sysinfo.py',
  'utils.py',
  'getlearngive.png',
  'landscape_dark.png',
]

install_emptydir(moduledir / 'css')
install_data('css/style.css',install_dir: join_paths(moduledir,'css'))
install_data(sources, install_dir: moduledir)
