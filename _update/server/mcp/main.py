from fastmcp import FastMCP

mcp = FastMCP()

@mcp.tool
def sum_a_b(a, b):
    """
    Возвращает сумму двух параметров a и b
    args:
        a: int
        b: int
    return: a + b
    """
    return a + b

# Укажите explicit transport=http
mcp.run(transport="http", host="0.0.0.0", port=8005)