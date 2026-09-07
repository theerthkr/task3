from face_search.social_leads import extract_social_links, leads_for_match


def test_extracts_social_links_only():
    html = '''
    <a href="https://github.com/janedoe">gh</a>
    <a href="https://www.linkedin.com/in/janedoe">li</a>
    <a href="https://example.com/about">about</a>
    <a href="/relative/path">rel</a>
    <a href="https://github.com/janedoe">dup</a>
    '''
    out = extract_social_links("https://example.com", html)
    assert [(l["platform"], l["handle"]) for l in out] == [
        ("linkedin", "janedoe"),
        ("github", "janedoe"),
    ]


def test_empty_html_gives_no_leads():
    assert extract_social_links("https://example.com", "") == []


def test_match_without_page_url():
    assert leads_for_match({"page_url": ""}, html="<a href='https://x.com/a'>x</a>") == []
