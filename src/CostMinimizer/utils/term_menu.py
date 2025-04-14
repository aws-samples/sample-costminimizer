from ..utils.system_validations import determine_os


def launch_terminal_menu(list_menus, title, subtitle, multi_select=True, show_multi_select_hint=True, show_search_hint=True, exit_when_finished=True) :
    # IF USING CURSES MENU
    # menu = CursesMenu.make_selection_menu(list_menus,"Select an option")
    #menu.show()
    #menu.join()
    #return menu.selected_option

    operating_system = determine_os()

    if operating_system == 'Linux' or operating_system == "Darwin":
        from simple_term_menu import TerminalMenu
        terminal_menu = TerminalMenu(list_menus, title=title,  multi_select=multi_select, search_key="/")
        menu_entry_index = terminal_menu.show()

        # if isinstance(menu_entry_index, int):
        #     menu_entry_index = (menu_entry_index,)

        if isinstance(menu_entry_index, int):
            index = menu_entry_index
            options_selected = (list_menus[index], index)
        else:
            options_selected = []
            for index in menu_entry_index:
                options_selected.append((list_menus[index], index))

        return options_selected
    else:
        #operating_system == 'Darwin' or operating_system == 'Windows':
        from pick import pick
        options_selected = pick(list_menus, title, multiselect=multi_select, min_selection_count=1)
        return options_selected

