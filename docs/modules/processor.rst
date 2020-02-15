processor
=========

The abstract class :class:`~.processor.Processor` can execute a given (parsed) NetQASM subroutine.
The method :meth:`~.processor.Processor.get_next_subroutine` needs to be overriden to define how the processor should fetch the next subroutine to execute.
By default no quantum operations are actually performed but also needs to be overriden.

The class :class:`~.processor.FromStringProcessor` implementes the method :meth:`~.processor.Processor.get_next_subroutine` by simply getting subroutines from a queue of subroutines submitted by :meth:`~.processor.FromStringProcessor.put_subroutine`.

.. automodule:: netqasm.processor
   :members:
   :undoc-members:
