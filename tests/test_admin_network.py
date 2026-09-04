import re


def _csrf_from(html: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_rates_page_shows_current_amounts(client) -> None:
    response = client.get("/admin/network/rates")

    assert response.status_code == 200
    assert "1 уровень" in response.text
    assert "2 уровень" in response.text
    assert "3 уровень" in response.text


def test_rates_submit_updates_amounts(client) -> None:
    csrf = _csrf_from(client.get("/admin/network/rates").text)

    response = client.post(
        "/admin/network/rates",
        data={"amount_1": "600.50", "amount_2": "225.25", "amount_3": "50.00", "csrf": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get("/admin/network/rates").text
    assert 'value="600.50"' in page
    assert 'value="225.25"' in page
    assert 'value="50.00"' in page

    csrf = _csrf_from(page)
    client.post(
        "/admin/network/rates",
        data={"amount_1": "500", "amount_2": "200", "amount_3": "100", "csrf": csrf},
    )


def test_rates_submit_rejects_negative_amount(client) -> None:
    csrf = _csrf_from(client.get("/admin/network/rates").text)

    response = client.post(
        "/admin/network/rates",
        data={"amount_1": "-1", "amount_2": "5", "amount_3": "5", "csrf": csrf},
    )

    assert response.status_code == 400
    assert "не может быть отрицательной" in response.text


def test_rates_submit_rejects_bad_csrf(client) -> None:
    response = client.post(
        "/admin/network/rates",
        data={"amount_1": "10", "amount_2": "5", "amount_3": "5", "csrf": "wrong"},
    )

    assert response.status_code == 400
    assert "Обновите страницу" in response.text
