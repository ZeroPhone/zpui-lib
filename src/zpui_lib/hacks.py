def zpui_hacks():
    #Py2-3 hax to make basestring work
    try:
        basestring
    except:
        import builtins
        builtins.basestring = str
