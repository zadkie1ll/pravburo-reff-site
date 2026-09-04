def test_admin_panel_lists_sections(client) -> None:
    response = client.get("/admin")

    assert response.status_code == 200
    assert "/admin/network/rates" in response.text
    assert "/admin/network/tree" in response.text
