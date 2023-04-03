import os
import re
import json
from unittest.mock import NonCallableMagicMock
from pydantic import BaseModel
from typing import Dict, List, Union


class Recipe(BaseModel):
    name: str  # The primary item crafted
    input_items: Dict[str, int]  # {item_name, quantity}
    output_items: Dict[str, int]  # {item_name, quantity}
    craft_time_seconds: float
    power_required: float = None

    @property
    def products_per_minute(self):
        return self.output_items[self.name] / (self.craft_time_seconds / 60)

    @property
    def power_per_minute(self):
        if self.power_required is None:
            return None
        return self.power_required / (self.craft_time_seconds / 60)

    @property
    def put(self):
        output = {
            'name': self.name,
            'input_items': self.input_items,
            'output_items': self.output_items,
            'craft_time_seconds': self.craft_time_seconds,
            'power_required': self.power_required,
        }
        return output

    @classmethod
    def build(cls, dct):
        content = {}
        if 'name' in dct:
            content['name'] = dct['name']

        if 'input_items' in dct:
            content['input_items'] = dct['input_items']

        if 'output_items' in dct:
            content['output_items'] = dct['output_items']

        if 'craft_time_seconds' in dct:
            content['craft_time_seconds'] = dct['craft_time_seconds']

        if 'power_required' in dct:
            content['power_required'] = dct['power_required']

        return cls(**content)


class Item(BaseModel):
    name: str
    recipes: List[Recipe]
    ideal_recipe_index: int = None

    @property
    def ideal_recipe(self):
        index = self.ideal_recipe_index or 0
        return self.recipes[index]

    @property
    def put(self):
        output = {
            'name': self.name,
            'recipes': [r.put for r in self.recipes],
            'ideal_recipe_index': self.ideal_recipe_index,
        }
        return output

    @classmethod
    def build(cls, dct):
        content = {}
        if 'name' in dct:
            content['name'] = dct['name']

        if 'recipes' in dct:
            content['recipes'] = [Recipe.build(r) for r in dct['recipes']]

        if 'ideal_recipe_index' in dct:
            content['ideal_recipe_index'] = dct['ideal_recipe_index']

        return cls(**content)


class ItemQuery:
    def __init__(self):
        self.items_path = 'etc/item_database.json'
        self.items = []

    def save_items_db(self):
        details = sorted(self.items, key=lambda x: x.name)
        with open(self.items_path, 'w') as df:
            df.write(json.dumps([i.put for i in details], indent=4))

    def load_items_db(self):
        with open(self.items_path, 'r') as df:
            data = json.load(df)
        for item in data:
            self.items.append(Item.build(item))


class ThroughputCalculator:
    def __init__(self, item_query:ItemQuery, name:str):
        self.item_query = item_query
        self.name = name
        self.item = self.find_item(name=name)
        self.output = []

    def find_item(self, name):
        for item in self.item_query.items:
            if name == item.name:
                return item

    def calculate_crafter_requirements(self, throughput_rate_per_minute:int, name=None):
        if name is None:
            item = self.item
        else:
            item = self.find_item(name=name)
        count = 0
        throughput = 0
        while throughput < throughput_rate_per_minute:
            count += 1
            throughput = count * item.ideal_recipe.products_per_minute
        return count

    def _format_recipie_table_item(self, name, throughput_rate_per_minute, output, total_throughput={}):
        item = self.find_item(name=name)
        if item is None:
            return
        output.append('\n---\n')
        crafters_count = self.calculate_crafter_requirements(throughput_rate_per_minute=throughput_rate_per_minute)
        recipe = item.ideal_recipe
        output.append(f"Process for {name}:")
        output.append(f"Number of crafters: {crafters_count}")
        output.append('Requirements:')
        for item, count in recipe.input_items.items():
            output.append(f"    {item} = {count} ({count * crafters_count} U/s)")
        output.append('Produces:')
        for item, count in recipe.output_items.items():
            output.append(f"    {item} = {count} ({count * crafters_count} U/s)")
        output.append('Process:')
        output.append(f"    Time = {recipe.craft_time_seconds} (seconds)")
        throughput = recipe.products_per_minute * crafters_count
        output.append(f"    Items per minute = {recipe.products_per_minute} ({throughput}) (Units / minute)")
        ppm = recipe.power_per_minute * crafters_count if recipe.power_per_minute is not None else '---'
        output.append(f"    Power per minute = {recipe.power_per_minute} ({ppm}) (Power / minute)")

        if name not in total_throughput:
            total_throughput[name] = 0
        total_throughput[name] += throughput

        for item_name, count in recipe.input_items.items():
            updated_throughput = self._format_recipie_table_item(
                name=item_name,
                throughput_rate_per_minute=count * crafters_count,
                output=output,
                total_throughput=total_throughput
            )
            if updated_throughput is None:
                continue
            total_throughput = updated_throughput

        return total_throughput

    def _total_throughput_table_items(self, total_throughput, output):
        output.append('\n---\n')
        output.append('Total throughputs:')
        for name, throughput  in total_throughput.items():
            item = self.find_item(name=name)
            crafters_count = self.calculate_crafter_requirements(throughput_rate_per_minute=throughput)
            recipe = item.ideal_recipe
            output.append(f"    {name} = {throughput} (U/s)")
            output.append(f"    Crafters = {crafters_count}")
            ppm = recipe.power_per_minute * crafters_count if recipe.power_per_minute is not None else '---'
            output.append(f"    Power per minute = {ppm} (Power / minute)")
            output.append('\n---\n')



    def return_calculation(self, throughput_rate_per_minute:int):
        output = [f"Process for {self.name}:"]
        recipe = self.item.ideal_recipe
        output.append('Requirements:')
        for item, count in recipe.input_items.items():
            output.append(f"    {item} = {count}")
        output.append('Produces:')
        for item, count in recipe.output_items.items():
            output.append(f"    {item} = {count}")
        output.append('Process:')
        output.append(f"    Time = {recipe.craft_time_seconds} (seconds)")
        output.append(f"    Items per minute = {recipe.products_per_minute} (Units / minute)")
        output.append(f"    Power per minute = {recipe.power_per_minute} (Power / minute)")

        output.append('\n---\n')

        output.append('Throughput calculations:')
        total_throughput = self._format_recipie_table_item(name=self.name, throughput_rate_per_minute=throughput_rate_per_minute, output=output)
        self._total_throughput_table_items(total_throughput=total_throughput, output=output)

        self.output = output

    def save_calculation_output(self):
        with open('deleteme.txt', 'w') as tf:
            tf.write('\n'.join(self.output))

    def display_calculation_output(self):
        print('\n'.join(self.output))


if __name__ == '__main__':
    iq = ItemQuery()
    iq.load_items_db()

    tc = ThroughputCalculator(item_query=iq, name='reinforced_iron_plate')
    tc.return_calculation(throughput_rate_per_minute=100)
    tc.save_calculation_output()
