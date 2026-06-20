"""
croe.play.exception 异常继承关系单测覆盖

目标: 锁定异常的类层级,防止新增子类搞错基类导致 except 失效。
- APIAssertException 必须继承 AssertionError (assert 协议兼容)
- RetryException 必须继承 Exception 而非 PlayExecutionError (走"重试"特殊路径)
- PlayExecutionError 是基础执行异常
- ActionError / AssertionFailedError / VariableError 必须继承 PlayExecutionError
"""
import pytest


class TestAPIAssertException:
    """APIAssertException: API 断言失败,继承 AssertionError。"""

    def test_inherits_assertion_error(self):
        from croe.play.exception import APIAssertException
        assert issubclass(APIAssertException, AssertionError)

    def test_can_be_raised_and_caught_by_assertion(self):
        from croe.play.exception import APIAssertException
        with pytest.raises(AssertionError):
            raise APIAssertException("断言失败")

    def test_carries_message(self):
        from croe.play.exception import APIAssertException
        err = APIAssertException("expect 200, got 500")
        assert "expect 200" in str(err)

    def test_can_be_raised_with_no_message(self):
        """异常应允许无参构造 (因为源码用 ... 替代 __init__)。"""
        from croe.play.exception import APIAssertException
        err = APIAssertException()
        assert err is not None


class TestRetryException:
    """RetryException: 重试信号,继承 Exception 而非 PlayExecutionError。

    业务约定: RetryException 是控制流信号,不应被统一 except PlayExecutionError 吞掉。
    """

    def test_inherits_exception(self):
        from croe.play.exception import RetryException
        assert issubclass(RetryException, Exception)

    def test_does_not_inherit_play_execution_error(self):
        """RetryException 不能是 PlayExecutionError 子类,否则会被重试逻辑外层吞掉。"""
        from croe.play.exception import RetryException, PlayExecutionError
        assert not issubclass(RetryException, PlayExecutionError)

    def test_carries_message(self):
        from croe.play.exception import RetryException
        err = RetryException("rate limit, retry later")
        assert "rate limit" in str(err)


class TestPlayExecutionError:
    """PlayExecutionError: UI 执行基础异常。"""

    def test_inherits_exception(self):
        from croe.play.exception import PlayExecutionError
        assert issubclass(PlayExecutionError, Exception)

    def test_default_message_is_empty(self):
        from croe.play.exception import PlayExecutionError
        err = PlayExecutionError()
        assert isinstance(err, PlayExecutionError)

    def test_carries_custom_message(self):
        from croe.play.exception import PlayExecutionError
        err = PlayExecutionError("页面加载失败")
        assert "页面加载失败" in str(err)


class TestActionError:
    """ActionError: 操作执行异常 (click/input/navigate 等)。"""

    def test_inherits_play_execution_error(self):
        from croe.play.exception import ActionError, PlayExecutionError
        assert issubclass(ActionError, PlayExecutionError)

    def test_inherits_exception(self):
        from croe.play.exception import ActionError
        assert issubclass(ActionError, Exception)

    def test_is_caught_by_play_execution_error_handler(self):
        """业务约定: except PlayExecutionError 能抓到 ActionError。"""
        from croe.play.exception import ActionError, PlayExecutionError
        try:
            raise ActionError("selector not found")
        except PlayExecutionError as e:
            assert "selector" in str(e)
        else:
            pytest.fail("ActionError 未能被 PlayExecutionError 捕获")


class TestAssertionFailedError:
    """AssertionFailedError: 断言失败 (UI 业务断言,非 API 协议断言)。"""

    def test_inherits_play_execution_error(self):
        from croe.play.exception import AssertionFailedError, PlayExecutionError
        assert issubclass(AssertionFailedError, PlayExecutionError)

    def test_distinct_from_api_assert(self):
        """AssertionFailedError 和 APIAssertException 是不同分支,不能互通。"""
        from croe.play.exception import (
            APIAssertException,
            AssertionFailedError,
            PlayExecutionError,
        )
        assert issubclass(AssertionFailedError, PlayExecutionError)
        assert issubclass(APIAssertException, AssertionError)
        assert not issubclass(AssertionFailedError, APIAssertException)
        assert not issubclass(APIAssertException, AssertionFailedError)

    def test_carries_message(self):
        from croe.play.exception import AssertionFailedError
        err = AssertionFailedError("expected '登录成功' in page text")
        assert "登录成功" in str(err)


class TestVariableError:
    """VariableError: 变量缺失/解析错误。"""

    def test_inherits_play_execution_error(self):
        from croe.play.exception import VariableError, PlayExecutionError
        assert issubclass(VariableError, PlayExecutionError)

    def test_carries_message(self):
        from croe.play.exception import VariableError
        err = VariableError("变量 ${token} 未定义")
        assert "${token}" in str(err)


class TestExceptionHierarchyOverall:
    """整体层级契约,防止误改。"""

    def test_all_ui_execution_errors_share_base(self):
        """ActionError / AssertionFailedError / VariableError 都应能一处捕获。"""
        from croe.play.exception import (
            ActionError,
            AssertionFailedError,
            PlayExecutionError,
            VariableError,
        )
        for err_cls in (ActionError, AssertionFailedError, VariableError):
            assert issubclass(err_cls, PlayExecutionError), (
                f"{err_cls.__name__} 应继承 PlayExecutionError"
            )

    def test_exception_classes_are_distinct(self):
        """所有 6 个异常类两两不同。"""
        from croe.play.exception import (
            APIAssertException,
            ActionError,
            AssertionFailedError,
            PlayExecutionError,
            RetryException,
            VariableError,
        )
        classes = {
            APIAssertException,
            ActionError,
            AssertionFailedError,
            PlayExecutionError,
            RetryException,
            VariableError,
        }
        assert len(classes) == 6
