class Position:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Velocity:
    def __init__(self, dx, dy):
        self.dx = dx
        self.dy = dy

class Sprite:
    def __init__(self, surface):
        self.surface = surface
    
    def draw(self, screen, x, y):
        screen.blit(self.surface, (x, y))

# New Rotation component
class Rotation:
    def __init__(self, angle=0.0, speed=0.0):
        """ Initializes the Rotation component.

        Args:
            angle (float): Initial angle in degrees. Defaults to 0.0.
            speed (float): Initial rotational speed in degrees per second. Defaults to 0.0.
        """
        self.angle = angle
        self.speed = speed 