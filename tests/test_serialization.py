from collections import namedtuple
from marshmallow import decorators, fields, Schema
from marshmallow_polyfield.polyfield import PolyField, ExplicitPolyField
import pytest
from tests.shapes import (
    Rectangle,
    Triangle,
    shape_schema_serialization_disambiguation,
    shape_schema_deserialization_disambiguation,
)
from tests.polyclasses import ShapePolyField, with_all


def with_both_shapes(func):
    return with_all(
        PolyField(
            serialization_schema_selector=shape_schema_serialization_disambiguation,
            deserialization_schema_selector=shape_schema_deserialization_disambiguation
        ),
        ShapePolyField()
    )(func)


def test_serializing_named_tuple():
    Point = namedtuple('Point', ['x', 'y'])

    field = fields.Field()

    p = Point(x=4, y=2)

    assert field.serialize('x', p) == 4


def test_serializing_named_tuple_with_meta():
    Point = namedtuple('Point', ['x', 'y'])
    p = Point(x=4, y=2)

    class PointSerializer(Schema):
        class Meta:
            fields = ('x', 'y')

    serialized = PointSerializer().dump(p)
    assert serialized['x'] == 4
    assert serialized['y'] == 2


@with_both_shapes
def test_serializing_polyfield_rectangle(field):
    rect = Rectangle("blue", 4, 10)
    Sticker = namedtuple('Sticker', ['shape', 'image'])
    marshmallow_sticker = Sticker(rect, "marshmallow.png")
    rect_dict = field.serialize('shape', marshmallow_sticker)

    assert rect_dict == {"length": 4, "width": 10, "color": "blue"}


@with_both_shapes
def test_serializing_polyfield_None(field):
    Sticker = namedtuple('Sticker', ['shape', 'image'])
    marshmallow_sticker = Sticker(None, "marshmallow.png")
    rect_dict = field.serialize('shape', marshmallow_sticker)

    assert rect_dict is None


@with_all(
    PolyField(
        serialization_schema_selector=shape_schema_serialization_disambiguation,
        deserialization_schema_selector=shape_schema_deserialization_disambiguation,
        many=True
    ),
    ShapePolyField(many=True)
)
def test_serializing_polyfield_many(field):
    rect = Rectangle("blue", 4, 10)
    tri = Triangle("red", 1, 100)
    StickerCollection = namedtuple('StickerCollection', ['shapes', 'image'])
    marshmallow_sticker_collection = StickerCollection([rect, tri], "marshmallow.png")
    shapes = field.serialize('shapes', marshmallow_sticker_collection)
    expected_shapes = [
        {"length": 4, "width": 10, "color": "blue"},
        {"base": 1, "height": 100, "color": "red"}
    ]
    assert shapes == expected_shapes


@with_both_shapes
def test_invalid_polyfield(field):
    Sticker = namedtuple('Sticker', ['shape', 'image'])
    with pytest.raises(TypeError):
        field.serialize('shape', Sticker(3, 3))


@with_both_shapes
def test_serializing_polyfield_by_parent_type(field):
    rect = Rectangle("blue", 4, 10)
    Sticker = namedtuple('Sticker', ['shape', 'image', 'type'])
    marshmallow_sticker = Sticker(rect, "marshmallow.png", 'rectangle')
    rect_dict = field.serialize('shape', marshmallow_sticker)

    assert rect_dict == {"length": 4, "width": 10, "color": "blue"}


def test_serializing_with_modification():
    import marshmallow

    def create_label_schema(schema):
        class LabelSchema(marshmallow.Schema):
            type = marshmallow.fields.String()
            value = schema()

        return LabelSchema

    class_to_schema = {
        str: marshmallow.fields.String,
        int: marshmallow.fields.Integer,
    }

    name_to_class = {
        'str': str,
        'int': int,
    }

    class_to_name = {
        cls: name
        for name, cls in name_to_class.items()
    }

    def serialization_schema(base_object, parent_obj):
        cls = type(base_object)
        schema = class_to_schema[cls]

        label_schema = create_label_schema(schema=schema)

        return label_schema()

    def serialization_value(base_object, parent_obj):
        cls = type(base_object)
        name = class_to_name[cls]

        return {'type': name, 'value': base_object}

    def deserialization_schema(object_dict, parent_object_dict):
        name = object_dict['type']
        cls = name_to_class[name]
        schema = class_to_schema[cls]

        return schema()

    def deserialization_value(object_dict, parent_object_dict):
        return object_dict['value']

    class TopClass:
        def __init__(self, polyfield):
            self.polyfield = polyfield

        def __eq__(self, other):
            if type(self) != type(other):
                return False

            return self.polyfield == other.polyfield

    class TopSchema(marshmallow.Schema):
        polyfield = PolyField(
            serialization_schema_selector=serialization_schema,
            deserialization_schema_selector=deserialization_schema,
            serialization_value_modifier=serialization_value,
            deserialization_value_modifier=deserialization_value,
        )

        @marshmallow.decorators.post_load
        def make_object(self, data, many, partial):
            return TopClass(**data)

    top_schema = TopSchema()

    top_class_str_example = TopClass(polyfield='abc')
    top_class_str_example_dumped = top_schema.dump(top_class_str_example)
    print(top_class_str_example_dumped)
    top_class_str_example_loaded = top_schema.load(top_class_str_example_dumped)
    assert top_class_str_example_loaded == top_class_str_example

    print('---')

    top_class_int_example = TopClass(polyfield=42)
    top_class_int_example_dumped = top_schema.dump(top_class_int_example)
    print(top_class_int_example_dumped)
    top_class_int_example_loaded = top_schema.load(top_class_int_example_dumped)
    assert top_class_int_example_loaded == top_class_int_example


def test_serializing_with_modification_ExplicitPolyField():
    class TopClass:
        def __init__(self, polyfield):
            self.polyfield = polyfield

        def __eq__(self, other):
            if type(self) != type(other):
                return False

            return self.polyfield == other.polyfield

    class TopSchema(Schema):
        polyfield = ExplicitPolyField(
            class_to_schema_mapping={
                str: fields.String,
                int: fields.Integer,
            },
        )

        @decorators.post_load
        def make_object(self, data, many, partial):
            return TopClass(**data)

    top_schema = TopSchema()

    top_class_str_example = TopClass(polyfield='abc')
    top_class_str_example_dumped = top_schema.dump(top_class_str_example)
    print(top_class_str_example_dumped)
    top_class_str_example_loaded = top_schema.load(top_class_str_example_dumped)
    assert top_class_str_example_loaded == top_class_str_example

    print('---')

    top_class_int_example = TopClass(polyfield=42)
    top_class_int_example_dumped = top_schema.dump(top_class_int_example)
    print(top_class_int_example_dumped)
    top_class_int_example_loaded = top_schema.load(top_class_int_example_dumped)
    assert top_class_int_example_loaded == top_class_int_example


explicit_poly_field = ExplicitPolyField(
    class_to_schema_mapping={
        str: fields.String,
        int: fields.Integer,
        dict: fields.Dict,
    },
)


ExplicitPolyFieldExample = namedtuple(
    'ExplicitPolyFieldExample',
    [
        'type_name',
        'value',
        'layer',
        'field',
    ],
)


def create_explicit_poly_field_example(type_name, value, field):
    return ExplicitPolyFieldExample(
        type_name=type_name,
        value=value,
        layer={'type': type_name, 'value': value},
        field=field,
    )


parametrize_explicit_poly_field_type_name_and_value = pytest.mark.parametrize(
    ['example'],
    [
        [create_explicit_poly_field_example(
            type_name='str',
            value='red',
            field=fields.String,
        )],
        [create_explicit_poly_field_example(
            type_name='int',
            value=42,
            field=fields.Integer,
        )],
        [create_explicit_poly_field_example(
            type_name='dict',
            value={'puppy': 3.9},
            field=fields.Dict,
        )],
    ],
)


@parametrize_explicit_poly_field_type_name_and_value
def test_serializing_explicit_poly_field(example):
    Point = namedtuple('Point', ['x', 'y'])
    p = Point(x=example.value, y=37)

    assert explicit_poly_field.serialize('x', p) == example.layer


@parametrize_explicit_poly_field_type_name_and_value
def test_serializing_explicit_poly_field_type_name(example):
    Point = namedtuple('Point', ['x', 'y'])
    p = Point(x=example.value, y=37)

    serialized = explicit_poly_field.serialize('x', p)
    assert serialized['type'] == example.type_name


@parametrize_explicit_poly_field_type_name_and_value
def test_serializing_explicit_poly_field_type_name(example):
    Point = namedtuple('Point', ['x', 'y'])
    p = Point(x=example.value, y=37)

    serialized = explicit_poly_field.serialize('x', p)
    assert serialized['value'] is example.value


@parametrize_explicit_poly_field_type_name_and_value
def test_deserializing_explicit_poly_field_value(example):
    assert explicit_poly_field.deserialize(example.layer) is example.value


@parametrize_explicit_poly_field_type_name_and_value
def test_deserializing_explicit_poly_field_field_type(example):
    # TODO: Checking the type only does so much, really want to compare
    #       the fields but they don't implement == so we'll have to code
    #       that up to check it.
    assert (
        type(explicit_poly_field.deserialization_schema_selector(
            example.layer,
            {'x': example.layer},
        ))
        is type(example.field())
    )

