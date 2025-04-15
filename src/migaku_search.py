
def searchTerm(self: QWebEngineView) -> None:
    text = selectedText(self)
    if text:
        text = re.sub(r'\[[^\]]+?\]', '', text)
        text = text.strip()
        if not migaku_dictionary.get_visible_dictionary():
            midict.dictionaryInit([text])

        dictionary = migaku_dictionary.get()
        dictionary.ensureVisible()
        dictionary.initSearch(text)
        if self.title == 'main webview':
            if mw.state == 'review':
                dictionary.dict.setReviewer(mw.reviewer)
        elif self.title == 'editor':
            target = getTarget(type(self.parentEditor.parentWindow).__name__)
            dictionary.dict.setCurrentEditor(self.parentEditor, target=target or "")
        midict.showAfterGlobalSearch()
