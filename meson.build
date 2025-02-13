project('kramden-provision', version: '0.0.4')
pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())

gnome = import('gnome')

subdir('data')
subdir('src')
subdir('scripts')
#subdir('tests')

#python3 = import('python').find_installation()

#test('unittests', python3, args : ['-m', 'unittest', 'discover'])
#
gnome.post_install(
    gtk_update_icon_cache: true,
  update_desktop_database: true,
)
