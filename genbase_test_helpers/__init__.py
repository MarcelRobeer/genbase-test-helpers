# =========================
# Temporary class to hold a `il.AbstractClassifier` from callable
# =========================

from typing import Any, Callable, FrozenSet, Iterable, List, Sequence, Tuple, TypeVar

import numpy as np

from instancelib import AbstractClassifier, Instance, InstanceProvider, LabelProvider
from instancelib.labels.encoder import DictionaryEncoder
from instancelib.typehints.typevars import KT, LT, RT, VT
from instancelib.utils.chunks import divide_iterable_in_lists
from instancelib.utils.func import zip_chain

IT = TypeVar("IT", bound="Instance[Any, Any, Any, Any]", covariant=True)
DT = str


class DeterministicTextClassifier(AbstractClassifier):
    def __init__(self, predict_function: Callable[[List[DT]], np.ndarray], target_labels: Iterable[LT]):
        self.predict_function = predict_function
        self.set_target_labels(target_labels)

    @classmethod
    def from_callable(cls, predict_function: Callable[[DT], np.ndarray], target_labels: Iterable[LT]):
        def batched_predict_function(instances: List[DT]) -> np.ndarray:
            return np.vstack([predict_function(ins) for ins in instances])

        return cls(batched_predict_function, target_labels)

    @classmethod
    def from_batched_callable(cls, predict_function: Callable[[List[DT]], np.ndarray], target_labels: Iterable[LT]):
        return cls(predict_function, target_labels)

    def fit_instances(self, instances: Iterable[Instance[KT, DT, VT, RT]], labels: Iterable[Iterable[LT]]) -> None:
        return None

    def fit_provider(
        self, provider: InstanceProvider[IT, KT, DT, VT, RT], labels: LabelProvider[KT, LT], batch_size: int = 200
    ) -> None:
        return None

    def _pred_proba_batch_raw(self, batch: Iterable[Instance[KT, DT, VT, Any]]) -> Tuple[Sequence[KT], np.ndarray]:
        x_keys = [ins.identifier for ins in batch]
        x_instances = [ins.data for ins in batch]
        y_pred = self.predict_function(x_instances)
        return x_keys, y_pred

    def _pred_proba_batch(
        self, batch: Iterable[Instance[KT, DT, VT, Any]]
    ) -> Sequence[Tuple[KT, FrozenSet[Tuple[LT, float]]]]:
        x_keys, y_pred = self._pred_proba_batch_raw(batch)
        return x_keys, self.encoder.decode_proba_matrix(y_pred)

    def _pred_batch(self, batch: Iterable[Instance[KT, DT, VT, Any]]) -> Sequence[Tuple[KT, FrozenSet[LT]]]:
        x_keys, y_pred = self._pred_proba_batch_raw(batch)
        return x_keys, self.encoder.decode_matrix(np.argmax(y_pred, axis=1))

    @property
    def fitted(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return str(self.__class__.__name__)

    def set_target_labels(self, labels: Iterable[LT]) -> None:
        self.encoder = DictionaryEncoder({label: i for i, label in enumerate(labels)})

    def get_label_column_index(self, label: LT) -> int:
        return self.encoder.get_label_column_index(label)

    def predict_proba_instances_raw(self, instances: Iterable[Instance[KT, DT, VT, RT]], batch_size: int = 200):
        batches = divide_iterable_in_lists(instances, batch_size)
        yield from map(self._pred_proba_batch_raw, batches)

    def predict_proba_instances(
        self, instances: Iterable[Instance[KT, DT, VT, RT]], batch_size: int = 200
    ) -> Sequence[Tuple[KT, FrozenSet[Tuple[LT, float]]]]:
        batches = divide_iterable_in_lists(instances, batch_size)
        processed = zip_chain(map(self._pred_proba_batch, batches))
        return list(processed)

    def predict_instances(
        self, instances: Iterable[Instance[KT, DT, VT, RT]], batch_size: int = 200
    ) -> Sequence[Tuple[KT, FrozenSet[LT]]]:
        batches = divide_iterable_in_lists(instances, batch_size)
        processed = zip_chain(map(self._pred_batch, batches))
        return list(processed)

    def predict_provider(
        self, provider: InstanceProvider[IT, KT, DT, VT, RT], batch_size: int = 200
    ) -> Sequence[Tuple[KT, FrozenSet[LT]]]:
        return self.predict_instances(list(provider.values()), batch_size=batch_size)

    def predict_proba_provider_raw(self, provider: InstanceProvider[IT, KT, DT, VT, RT], batch_size: int = 200):
        return self.predict_proba_instances_raw(list(provider.values()), batch_size=batch_size)

    def predict_proba_provider(
        self, provider: InstanceProvider[IT, KT, DT, VT, Any], batch_size: int = 200
    ) -> Sequence[Tuple[KT, FrozenSet[Tuple[LT, float]]]]:
        return self.predict_proba_instances(list(provider.values()), batch_size=batch_size)


# =========================
# Actual code for pytest
# =========================

from typing import Union  # noqa: E402

from string import ascii_lowercase, digits, printable, punctuation  # noqa: E402
import random  # noqa: E402
import itertools  # noqa: E402

from instancelib import TextEnvironment  # noqa: E402

TEST_INSTANCES = list(printable)

TEST_LABELS = [
    ["punctuation"] if any(c in item for c in punctuation) else ["no_punctuation"] for item in TEST_INSTANCES
]

TEST_ENVIRONMENT = TextEnvironment.from_data(
    target_labels={"punctuation", "no_punctuation"},
    indices=list(range(len(TEST_INSTANCES))),
    data=TEST_INSTANCES,
    ground_truth=TEST_LABELS,
    vectors=None,
)

TEST_ENVIRONMENT.set_named_provider("test", TEST_ENVIRONMENT.dataset)


def predict_fn(instance: str) -> np.ndarray:
    return np.array([0.7, 0.3]) if any(c in instance for c in '!"#$%&()*+,-./:;<=>?@[^_`~aA') else np.array([0.3, 0.7])


TEST_MODEL = DeterministicTextClassifier.from_callable(predict_fn, ["punctuation", "no_punctuation"])


def corrupt(names: Union[Iterable[str], str]) -> Union[Iterable[str], str]:
    """Corrupt name of string(s)."""
    def corrupt_one(name):
        return f'{random.choice(ascii_lowercase + digits)}{name}'

    if isinstance(names, Iterable):
        return [corrupt_one(s) for s in names]
    return corrupt_one(names)


def random_combinations(iterable: Iterable[Any], start: int = 1):
    """Create random combinations of lengths start to length iterable."""
    pool = tuple(iterable)
    start = min(len(pool), max(0, start))

    def random_combination(r: int = 1):
        return [pool[i] for i in sorted(random.sample(range(len(pool)), r))]

    return [random_combination(i) for i in range(start, len(pool) + 1)]
