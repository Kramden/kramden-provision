project('kramden-provision', version: '0.0.1')

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
