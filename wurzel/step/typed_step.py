# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import abc
from collections.abc import Iterable
from logging import getLogger
from pathlib import Path
from types import NoneType
from typing import (
    Generic,
    Optional,
    Self,
    TypeAlias,
    TypeVar,
    Union,
    get_args,
)

import pandera.typing as patyp
from typing_inspect import get_origin

from wurzel.datacontract import PanderaDataFrameModel, PydanticModel
from wurzel.exceptions import ContractFailedException, StaticTypeError
from wurzel.path import PathToFolderWithBaseModels
from wurzel.step.settings import Settings
from wurzel.step.step import Step

# pylint: disable-next=invalid-name
MODEL_TYPE: TypeAlias = type[Union[PydanticModel, PanderaDataFrameModel]]
#  ^Should be a Intersection between DataModel & {BaseModel, DataFrameModel}
log = getLogger(__name__)
INCONTRACT = TypeVar("INCONTRACT")
OUTCONTRACT = TypeVar("OUTCONTRACT")


SETTS = TypeVar("SETTS", bound=Settings)


class TypedStep(Step, Generic[SETTS, INCONTRACT, OUTCONTRACT]):
    """Wurzel Pipeline Step.
    Makes use of **strong** typing. i.e. the types are not only hints.
    On `__init__` it will check annotations to make sure everything is correct.
    The only method that needs implementation is the run method.
    # Description:
    A (Knowledge / Wurzel) pipeline consists of many steps chained together.
    First data is gathered, then (>>) transformed etc.

    Each step (TypedStep) is defined by a triplet of Optional[Settings], Optional[input_d_type], output_d_type.
    Only if the output of a given step is compatible with the next, chaining is allowed.
    ## Settings
    The first part of the triplet. Is either None or a Subtype of wurzel.Settings (internally StepSettings).
    These settings are a special form of pydantic settings meaning they will try to load
    their values from the environment with the prefix `UPPERCASE_STEP_NAME`.
    For more information take a look at wurzel.step.settings
    ## Contract / Input-Output Classes
    The Inputs and outputs of TypedSteps are restricted.
    However they need to inherit from  wurzel.datacontract.DataModel
    There are already two subclasses in wurzel.datacontract implemented.
    Those extend both pydantic and pandera for typesafe objects and dataframes.
    Containers such as lists for both types are supported
    ### Input
    If the Input of a step is set to be None the step is a leaf and will always run.
    The `inputs` arg in the run method of the step can be ignored.
    ### Ouput
    The Step output can't be None.
    ### Input
    ## Example:
    ```python
    from wurzel.step import (
        PanderaDataFrameModel,
        TypedStep,
        PydanticModel,
        NoSettings
        )
    from pandera.typing import Series

    # Data Model definitions
    class MyData(PydanticModel):
        key: str = "Value"
    class MyTable(PanderaDataFrameModel):
        col1: Series[int]

    # Step definition
    class MyStep(TypedStep[NoSettings, None, list[MyData]]):
        def run(self, inpt: None) -> list[MyData]:
            return ...
    class MyOtherStep(TypedStep[None, list[MyData], MyTable]):
        def run(self, inpt: list[MyData]) -> MyTable:
            return ...
    ```
    """

    _internal_input_class: type[PathToFolderWithBaseModels]
    _internal_output_class: type[PathToFolderWithBaseModels]
    input_model_type: Union[MODEL_TYPE, list[MODEL_TYPE], None]
    output_model_type: Union[MODEL_TYPE, list[MODEL_TYPE], None]
    settings_class: type[SETTS]
    output_model_class: MODEL_TYPE
    input_model_class: MODEL_TYPE
    _supported_containers: Iterable[type[Iterable]] = (list, set, patyp.DataFrame)
    settings: SETTS

    def output_path(self, folder: Path) -> Path:
        """Used in generate dvc yml. Creates a path."""
        pth = folder / self.__class__.__name__
        return pth.with_suffix(self.output_model_class.kt_file_extension())

    @classmethod  #
    def _unpack_list_containers(
        cls,
        list_or_type: Union[list, type, None],
        containers: Optional[list[type[Iterable]]] = None,
    ) -> tuple[Optional[Iterable[type[Iterable]]], type]:
        """Unpacks the containers around a given nested Type.

        Args:
            list_or_type (Union[list, Type, None]): Type or container to try to unpack
            containers (Optional[list[Type[Iterable]]], optional): used in recursive calls. Defaults to None.

        Raises:
            StaticTypeError: Anyting goes wrong

        Returns:
            tuple[Optional[Iterable[Type[Iterable]]], Type]: (container types, type)

        """
        if containers is None:
            containers = []
        origin_t: Union[type[Iterable], type, None] = get_origin(list_or_type)
        if origin_t is None:
            # list_or_type is now a type/class
            if list_or_type is None:
                list_or_type = NoneType
            return containers, list_or_type  # type: ignore[return-value] # list_or_type is now a type.
        if origin_t in cls._supported_containers:
            containers.insert(0, origin_t)
        else:
            raise StaticTypeError(f"{origin_t} is not a supported container")
        if len(get_args(list_or_type)) == 1:
            # Unpack list_type
            return cls._unpack_list_containers(get_args(list_or_type)[0], containers)
        raise StaticTypeError(f"Cant handle type with {len(get_args(origin_t))} args")

    @classmethod  # pylint: disable-next=unused-private-member # used in __new__
    def _static_type_check_self(cls):
        """Confirms the type annotations of child classes TypedStep."""
        type_annotations = [get_args(parent) for parent in getattr(cls, "__orig_bases__", []) if get_args(parent)][0]
        if type_annotations == ():
            raise StaticTypeError(
                f"No type-annotation provided when creating subclass of {cls.__name__}" + f"Use: MyStep({cls.__name__}[INPUT_T, OUTPUT_T])"
            )
        cls._prepare_datamodels(type_annotations)
        if not issubclass(cls.settings_class, (Settings, NoneType)):
            raise StaticTypeError("Settings provided in TypedStep[<>, ...]" + " is not a subclass of settings_class")
        _ = cls._unpack_list_containers(cls.input_model_type)
        out_t = cls._unpack_list_containers(cls.output_model_type)

        def has_no_annotation(c: list, t: type):
            return c == [] and t == NoneType

        if has_no_annotation(*out_t):
            raise StaticTypeError(f"Type-annotation for output of {cls.__name__}[..., None] can't be None")

    @classmethod
    def _prepare_datamodels(cls, type_annotations):
        cls.settings_class, cls.input_model_type, cls.output_model_type = type_annotations

    @classmethod  # pylint: disable-next=unused-private-member # used in __new__
    def _static_type_check_run(cls):
        """Confirms the type annotations of child classes run method.
        Currently allows missing type annotations with a warning.
        """
        # Since type annotation of class does not want list container
        # but run adds it, we add it manually
        expected_run_input = cls.input_model_type
        expected_signature_str = f"run(inputs: {expected_run_input}) -> {cls.output_model_type}:"
        try:
            if not cls.run.__annotations__:
                log.warning(f"The step {cls.__name__} has no types. This is not recommended!")
                log.info(f"Method signature should be {cls.__name__}.{expected_signature_str}:")
                # raise StaticTypeError(
                #    "incorrect function signature for run method:  no typing"
                # )
                annotations = {
                    "return": cls.output_model_type,
                    "inputs": expected_run_input,
                }
            else:
                annotations = cls.run.__annotations__.copy()
            run_retur = annotations.pop("return")
            if len(annotations) != 1:
                raise StaticTypeError("incorrect funtion signature (inputs) for run method: " + f"Expected one input, got {annotations}")
            _, run_input = annotations.popitem()
            run_input_cons, run_input_orig = cls._unpack_list_containers(run_input)
            run_retur_cons, run_retur_orig = cls._unpack_list_containers(run_retur)
            # construct type using only list instead of List
            return_annotation = run_retur_orig
            for container in run_retur_cons:
                return_annotation = container[return_annotation]
            input_annotation = run_input_orig
            for container in run_input_cons:
                input_annotation = container[input_annotation]
            # Check if inputs was in list
            if input_annotation != expected_run_input:
                raise StaticTypeError(
                    "Incorrect function signature (inputs) for run method:\n"
                    + f"\tis       run({run_input}) -> ...\n"
                    + f"\texpected {expected_signature_str}"
                )
            if return_annotation != cls.output_model_type:
                raise StaticTypeError(
                    "Incorrect function signature (return) for run method:\n"
                    + f"\tis       run(...) -> {run_retur.__name__}\n"
                    + f"\texpected {expected_signature_str}"
                )
        except IndexError as i:
            raise ContractFailedException("Could not get_args of either run inputs or return") from i
        except KeyError as k:
            raise ContractFailedException("Could not get annotations from run") from k

    def finalize(self) -> None:
        """Called after execution in Executor finished.

        Can be used for cleanup etc.

        One Example would be the retirement of collections in a db step.
        """

    def __new__(cls) -> Self:
        instance = super().__new__(cls)
        super().__init__(instance)
        # Get Input and output type from annotations
        # Get Type annotations, fallback to None if they don't exist
        # pylint: disable-next=no-member
        instance._static_type_check_self()

        cls._prepare_instance_datamodels(instance)

        instance._static_type_check_run()

        # Sadly we cant use type() or types.new_class for this.
        class InCls(PathToFolderWithBaseModels[instance.input_model_type]):
            """Used internally."""

        class OutCls(PathToFolderWithBaseModels[instance.output_model_type]):
            """Used internally."""

        instance._internal_input_class = InCls
        instance._internal_output_class = OutCls
        return instance

    @classmethod
    def _prepare_instance_datamodels(cls, instance):
        instance.input_model_class = (get_args(instance.input_model_type) or [instance.input_model_type])[-1]
        instance.output_model_class = (get_args(instance.output_model_type) or [instance.output_model_type])[-1]

    # super was called in __new__
    # pylint: disable-next=super-init-not-called
    def __init__(self) -> None:
        self.settings = self.settings_class()

    def add_required_step(self, step: "TypedStep"):
        """Add step to execution graph.

        Args:
            step (TypedStep) Step to add

        Raises:
            TypeError: On incompatible types

        """
        if self.input_model_type != step.output_model_type:
            raise TypeError(f"Cannot chain {self} to {step} ({step.output_model_type} -> {self.input_model_type})")
        super().add_required_step(step)

    def _traverse(self, set_of: set["TypedStep"]):
        set_of.add(self)
        for step in self.required_steps:
            TypedStep._traverse(step, set_of)
        return set_of

    def traverse(self) -> set["TypedStep"]:
        """Retrieve a set of all required steps
        including self.
        """
        return self._traverse(set())

    # pylint: disable=method-hidden
    @abc.abstractmethod
    def run(self, inpt: INCONTRACT) -> OUTCONTRACT:
        """Abstract function which is called with the parsed data in the shape of INCONTRACT.
        It's implementation should return the OUTCONTRACT
        ### It will be called mutliple times.

        """
        raise NotImplementedError()
