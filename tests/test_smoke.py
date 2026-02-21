from app.main import add

def test_add_valid():
    assert add(2, 3) == 5
    assert add(2.5, 3.5) == 6.0

def test_add_invalid():
    with pytest.raises(TypeError):
        add('a', 3)
    with pytest.raises(TypeError):
        add(2, 'b')
    with pytest.raises(TypeError):
        add('a', 'b')