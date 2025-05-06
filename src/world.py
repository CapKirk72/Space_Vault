class World:
    def __init__(self):
        self.entities = set()
        self.components = {}
        self.systems = []
        self.next_entity_id = 0
        
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