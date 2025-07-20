from .components import IsActive  # For pooling

class World:
    def __init__(self):
        self.entities = set()
        self.components = {}
        self.systems = []
        self.next_entity_id = 0
        self.pool_manager = PoolManager(self)
        self.atlas = None  # Set in main
        self.flight_plans = None
        
    def add_entity(self):
        entity = self.next_entity_id
        self.next_entity_id += 1
        self.entities.add(entity)
        return entity
        
    def remove_entity(self, entity):
        if entity in self.entities:
            self.entities.remove(entity)
            for component_type in list(self.components.keys()):
                if entity in self.components[component_type]:
                    del self.components[component_type][entity]
    
    def add_component(self, entity, component):
        component_type = type(component)
        if component_type not in self.components:
            self.components[component_type] = {}
        self.components[component_type][entity] = component
        
    def get(self, entity, component_type):
        if component_type in self.components and entity in self.components[component_type]:
            return self.components[component_type][entity]
        return None
        
    def add_system(self, system):
        self.systems.append(system)
        
    def update(self, dt):
        for system in self.systems:
            system.process(dt) 

class PoolManager:
    def __init__(self, world):
        self.world = world
        self.pools = {}  # type: list of eids
        self.reset_callbacks = {}  # type: callback function

    def register_pool(self, pool_type, size, create_callback, reset_callback):
        self.pools[pool_type] = []
        self.reset_callbacks[pool_type] = reset_callback
        for _ in range(size):
            eid = self.world.add_entity()
            create_callback(eid)
            self.world.add_component(eid, IsActive())  # Inactive by default
            self.pools[pool_type].append(eid)

    def get(self, pool_type):
        if self.pools[pool_type]:
            eid = self.pools[pool_type].pop(0)
            active_comp = self.world.get(eid, IsActive)
            if active_comp:
                active_comp.active = True  # Activate
            self.reset_callbacks[pool_type](eid)  # Reset state
            return eid
        return None  # Pool empty

    def return_to_pool(self, pool_type, eid):
        if eid in self.world.entities:
            active_comp = self.world.get(eid, IsActive)
            if active_comp:
                active_comp.active = False  # Deactivate
            self.reset_callbacks[pool_type](eid)  # Reset
            self.pools[pool_type].append(eid) 