import abc
import numpy as np
import scipy
import scipy.stats

# project imports
import gsvd
import resample
import exceptions


class ResampleTest(abc.ABC):
    """Abstract base class for the ResampleTest class set. Forces existence
    of certain functions.
    """

    _subclasses = {}

    # maps abbreviated user-specified classnames to full PLS variant names
    _pls_types = {
        "mct": "Mean-Centering Task PLS",
        # "mct_mg": "Mean-Centering Task PLS - Multi-Group",
        "nrt": "Non-Rotated Task PLS",
        "rb": "Regular Behaviour PLS",
        "mb": "Multiblock PLS",
        "nrb": "Non-Rotated Behaviour PLS",
        "nrmb": "Non-Rotated Multiblock PLS",
    }

    @abc.abstractmethod
    def __str__(self):
        pass

    @abc.abstractmethod
    def __repr__(self):
        pass

    # register valid decorated PLS/resample method as a subclass of
    # ResampleTest
    @classmethod
    def _register_subclass(cls, pls_method):
        def decorator(subclass):
            cls._subclasses[pls_method] = subclass
            return subclass

        return decorator

    # instantiate and return valid registered PLS method specified by user
    @classmethod
    def _create(cls, pls_method, *args, **kwargs):
        if pls_method not in cls._subclasses and pls_method in cls._pls_types:
            raise exceptions.NotImplementedError(
                f"Specified PLS/Resample method {cls._pls_types[pls_method]} "
                "has not yet been implemented."
            )
        elif pls_method not in cls._subclasses:
            raise ValueError(f"Invalid PLS/Resample method {pls_method}")
        return cls._subclasses[pls_method](*args, **kwargs)


@ResampleTest._register_subclass("mct")
@ResampleTest._register_subclass("rb")
class _ResampleTestTaskPLS(ResampleTest):
    """Class that runs permutation and bootstrap tests for Task PLS. When run,
    this class generates fields for permutation test information
    (permutation ratio, etc.) and for bootstrap test informtaion (confidence
    intervals, standard errors, bootstrap ratios, etc.).

    Parameters
    ----------
    X : np_array
        Input neural matrix/matrices for use with PLS. This matrix is passed
        in from the PLS class.
    U : np_array
        Left singular vectors of X.
    s : np_array
        Singular values for X. Used to compute permutation ratio.
    V : np_array
        Right singular vectors of X.
    cond_order : array-like
        Order vector(s) for conditions in X.
    preprocess : function, optional
        Preprocessing function used prior to running GSVD on X in
        PLS class. Used to preprocess resampled matrices in boostrap/
        permutation tests.
    nperm : int, optional
        Optional value specifying the number of iterations for the permutation
        test. Defaults to 1000.
    nboot : int, optional
        Optional value specifying the number of iterations for the bootstrap
        test. Defaults to 1000.
    ngroups : int, optional
        Value specifying the number of groups used in PLS. Specified by PLS
        class; defaults to 1.
    nonrotated : boolean, optional
        Not implememted yet.
    dist : 2-tuple of floats, optional
        Distribution values used for calculating the confidence interval in
        the bootstrap test. Defaults to (0.05, 0.95).

    Attributes
    ----------
    dist : 2-tuple of floats, optional
        Distribution values used for calculating the confidence interval in
        the bootstrap test. Defaults to (0.05, 0.95).
    permute_ratio : float
        Ratio of resampled values greater than observed values, divided by
        the number of iterations in the permutation test. A higher ratio
        indicates a higher level of randomness.
    conf_ints : 2-tuple of np_arrays
        Upper and lower element-wise confidence intervals for the resampled
        left singular vectors in a tuple.
    std_errs : np_array
        Element-wise standard errors for the resampled right singular vectors.
    boot_ratios : np_array
        NumPy array containing element-wise ratios of 

    """

    def __init__(
        self,
        X,
        Y,
        U,
        s,
        V,
        cond_order,
        preprocess=None,
        nperm=1000,
        nboot=1000,
        ngroups=1,
        dist=(0.05, 0.95),
        rotate_method=0,
    ):
        self.dist = dist

        self.permute_ratio = self._permutation_test(
            X,
            Y,
            U,
            s,
            V,
            cond_order,
            ngroups,
            nperm,
            preprocess=preprocess,
            rotate_method=rotate_method,
        )
        self.conf_ints, self.std_errs, self.boot_ratios = self._bootstrap_test(
            X,
            Y,
            U,
            s,
            V,
            cond_order,
            ngroups,
            nboot,
            preprocess=preprocess,
            rotate_method=rotate_method,
            dist=self.dist,
        )

    @staticmethod
    def _permutation_test(
        X,
        Y,
        U,
        s,
        V,
        cond_order,
        ngroups,
        niter,
        preprocess=None,
        rotate_method=0,
        threshold=1e-12,
    ):
        """Run permutation test on X. Resamples X (without replacement) based
        on condition order, runs PLS on resampled matrix, and computes the
        element-wise permutation ratio ((number of times permutation > observation)/`niter`.
        """
        # if ngroups > 1:
        #     raise exceptions.NotImplementedError(
        #         "Multi-group MCT-PLS is not yet implemented."
        #     )

        # singvals = np.empty((s.shape[0], niter))
        greatersum = np.zeros(s.shape)
        # s[np.abs(s) < threshold] = 0

        print("----Running Permutation Test----\n")
        for i in range(niter):
            if (i + 1) % 50 == 0:
                print(f"Iteration {i + 1}")
            # create resampled X matrix and get resampled indices

            X_new = resample.resample_without_replacement(X, cond_order)

            if Y is not None:
                Y_new = resample.resample_without_replacement(Y, cond_order)

            # X_new = np.empty(X.shape)
            # if Y is not None:
            #     Y_new = np.empty(Y.shape)
            # resampled_indices = []
            # group_sums = np.array([np.sum(i) for i in cond_order])
            # idx = 0
            # for i in range(ngroups):
            #     (
            #         X_new[idx : idx + group_sums[i],],
            #         res_ind,
            #     ) = resample.resample_without_replacement(
            #         X[idx : idx + group_sums[i],],
            #         cond_order,
            #         group_num=i,
            #         return_indices=True,
            #     )

            #     if Y is not None:
            #         Y_new[idx : idx + group_sums[i],] = Y[idx : idx + group_sums[i],][
            #             res_ind,
            #         ]
            #     resampled_indices.append(res_ind)
            #     idx += group_sums[i]
            # resampled_indices = np.array(resampled_indices)

            # X_new, resampled_indices = resample.resample_without_replacement(
            #     X, cond_order, return_indices=True
            # )

            # pass in preprocessing function (i.e. mean-centering) for use
            # after sampling

            if Y is None:
                permuted = preprocess(X_new, cond_order, return_means=False)

            else:
                permuted = preprocess(X_new, Y_new, cond_order)

            # if Y is None:
            #    X_new_means, X_new_mc = preprocess(
            #        X_new, cond_order=cond_order
            #    )  # , ngroups=ngroups)

            if rotate_method == 0:
                # run GSVD on mean-centered, resampled matrix
                # U_hat, s_hat, V_hat = gsvd.gsvd(permuted)

                # s_hat = gsvd.gsvd(permuted, compute_uv=False)
                s_hat = np.linalg.svd(permuted, compute_uv=False)
                # print(s_hat)
            elif rotate_method == 1:
                # U_hat, s_hat, V_hat = gsvd.gsvd(permuted)
                U_hat, s_hat, V_hat = np.linalg.svd(permuted, full_matrices=False)
                # procustes
                # U_bar, s_bar, V_bar = gsvd.gsvd(V.T @ V_hat)
                U_bar, s_bar, V_bar = np.linalg.svd(V.T @ V_hat, full_matrices=False)

                # print(X_new_mc.shape)
                rot = U_bar @ V.T
                V_rot = V_hat @ rot
                permuted_rot = permuted @ V_rot
                s_rot = np.sqrt(np.sum(np.power(permuted_rot.T, 2), axis=0))
                s_hat = np.copy(s_rot)
                # print(s_hat)
            elif rotate_method == 2:
                # use derivation equations to compute permuted singular values
                US_hat = permuted @ V
                s_hat = np.sqrt(np.sum(np.power(US_hat, 2), axis=0))

                # U_hat_, s_hat_, V_hat_ = gsvd.gsvd(X_new_mc)

                # gd = [float("{:.5f}".format(i)) for i in s_hat_]
                # der = [float("{:.5f}".format(i)) for i in s_hat]

                # print(f"GSVD: {gd}")
                # print(f"Derived: {der}")

                # U_hat = US_hat / s_hat
                # V_hat = np.linalg.inv(np.diag(s_hat)) @ (U.T @ X_new_mc)
                # print(s_hat)
            else:
                raise exceptions.NotImplementedError(
                    f"Specified rotation method ({rotate_method}) "
                    "has not been implemented."
                )

            # else:
            #     # compute condition-wise correlation matrices of resampled
            #     # input matrices and run GSVD
            #     R_new = preprocess(X_new, Y_new, cond_order)

            #     if rotate_method == 0:
            #         U_hat, s_hat, V_hat = gsvd.gsvd(R_new)
            #     elif rotate_method == 1:
            #         U_hat, s_hat, V_hat = gsvd.gsvd(X_new_mc)
            #         # procustes
            #         U_bar, s_bar, V_bar = gsvd.gsvd(V.T @ V_hat)
            #         s_pro = np.sqrt(np.sum(np.power(V_bar, 2), axis=0))
            #         s_hat = np.copy(s_pro)
            #     elif rotate_method == 2:
            #         # use derivation equations to compute permuted singular values
            #         US_hat = R_new @ V
            #         s_hat = np.sqrt(np.sum(np.power(US_hat, 2), axis=0))
            #         s_hat[np.abs(s_hat) < threshold] = 0

            #         # U_hat_, s_hat_, V_hat_ = gsvd.gsvd(R_new)
            #         # gd = [float("{:.5f}".format(i)) for i in s_hat_]
            #         # der = [float("{:.5f}".format(i)) for i in s_hat]

            #         # print(f"GSVD: {gd}")
            #         # print(f"Derived: {der}")
            #         # U_hat = US_hat / s_hat
            #         # V_hat = np.linalg.inv(np.siag(s_hat)) @ (U.T @ X_new_mc)
            #     else:
            #         raise exceptions.NotImplementedError(
            #             f"Specified rotation method ({rotate_method}) "
            #             "has not been implemented."
            #         )
            # insert s_hat into singvals tracking matrix
            # singvals[:, i] = s_hat
            # count number of times sampled singular values are
            # greater than observed singular values, element-wise
            # greatersum += s >= s_hat
            # print(s_hat >= s)
            # s_hat[np.abs(s_hat) < threshold] = 0
            greatersum += s_hat >= s

        permute_ratio = greatersum / niter

        print(f"real s: {s}")
        print(f"ratio: {permute_ratio}")
        return permute_ratio

    @staticmethod
    def _bootstrap_test(
        X,
        Y,
        U,
        s,
        V,
        cond_order,
        ngroups,
        niter,
        preprocess=None,
        rotate_method=0,
        dist=(0.05, 0.95),
    ):
        """Runs a bootstrap estimation on X matrix. Resamples X with
        replacement according to the condition order, runs PLS on the
        resampled X matrices, and computes `conf_int`, `std_errs`, and
        `boot_ratios`.
        """

        # allocate memory for sampled values
        left_sv_sampled = np.empty((niter, U.shape[0], U.shape[1]))
        right_sv_sampled = np.empty((niter, V.shape[0], V.shape[1]))

        # right_sum = np.zeros(X.shape[1], X.shape[1])
        # right_squares = np.zeros(X.shape[1], X.shape[1])
        print("----Running Bootstrap Test----\n")
        for i in range(niter):
            # print out iteration number every 50 iterations
            if (i + 1) % 50 == 0:
                print(f"Iteration {i + 1}")
            # create resampled X matrix and get resampled indices
            # resample within-group using cond_order for group size info
            # X_new = np.empty(X.shape)
            # if Y is not None:
            #     Y_new = np.empty(Y.shape)
            # resampled_indices = []
            # group_sums = np.array([np.sum(i) for i in cond_order])
            # idx = 0
            # for i in range(ngroups):
            #     (
            #         X_new[idx : idx + group_sums[i],],
            #         res_ind,
            #     ) = resample.resample_with_replacement(
            #         X[idx : idx + group_sums[i],],
            #         cond_order,
            #         group_num=i,
            #         return_indices=True,
            #     )
            #     # use same resampled indices for Y if applicable
            #     if Y is not None:
            #         Y_new[idx : idx + group_sums[i],] = Y[idx : idx + group_sums[i],][
            #             res_ind
            #         ]
            #     resampled_indices.append(res_ind)
            #     idx += group_sums[i]
            # resampled_indices = np.array(resampled_indices)

            X_new = resample.resample_with_replacement(X, cond_order)

            if Y is not None:
                Y_new = resample.resample_with_replacement(Y, cond_order)

            # pass in preprocessing function (e.g. mean-centering) for use
            # after sampling

            if Y is None:
                permuted = preprocess(X_new, cond_order, return_means=False)

            else:
                permuted = preprocess(X_new, Y_new, cond_order)

            # if Y is None:
            #     X_new_means, X_new_mc = preprocess(
            #         X_new, cond_order=cond_order
            #     )  # , ngroups=ngroups)

            if rotate_method == 0:
                # run GSVD on mean-centered, resampled matrix

                # U_hat, s_hat, V_hat = gsvd.gsvd(permuted)
                U_hat, s_hat, V_hat = np.linalg.svd(permuted, full_matrices=False)
                V_hat = V_hat.T
            elif rotate_method == 1:
                # U_hat, s_hat, V_hat = gsvd.gsvd(permuted)
                U_hat, s_hat, V_hat = np.linalg.svd(permuted, full_matrices=False)
                # procustes
                # U_bar, s_bar, V_bar = gsvd.gsvd(V.T @ V_hat)
                U_bar, s_bar, V_bar = np.linalg.svd(V.T @ V_hat, full_matrices=False)
                s_pro = np.sqrt(np.sum(np.power(V_bar, 2), axis=0))

            elif rotate_method == 2:
                # use derivation equations to compute permuted singular values
                # US_hat = X_new_mc @ V
                US_hat = V.T @ permuted.T
                s_hat = np.sqrt(np.sum(np.power(US_hat, 2), axis=0))
                U_hat_der = US_hat / s_hat
                V_hat = (np.linalg.inv(np.diag(s_hat)) @ (U.T @ permuted)).T
                # V_hat = (X_new_mc.T @ U_hat_der) / s_hat
                # potential fix for sign issues
                U_hat = U_hat_der
                # U_hat = (X_new_mc @ V_hat) / s_hat
                # U_hat_, s_hat_, V_hat_ = gsvd.gsvd(X_new_mc)

                # print("DERIVED\n")
                # print(U_hat_der)
                # print("=====================")
                # print("DOUBLE DERIVED\n")
                # print(s_hat)
                # print("----------------------")
                # print(s_hat_)
                # print("++++++++++++++++++++++")
            else:
                raise exceptions.NotImplementedError(
                    f"Specified rotation method ({rotate_method}) "
                    "has not been implemented."
                )

            # else:
            #     # compute condition-wise correlation matrices of resampled
            #     # input matrices and run GSVD
            #     R_new = preprocess(X_new, Y_new, cond_order)

            #     if rotate_method == 0:
            #         U_hat, s_hat, V_hat = gsvd.gsvd(R_new)

            #     elif rotate_method == 1:
            #         pass

            #     elif rotate_method == 2:
            #         US_hat = R_new @ V
            #         s_hat = np.sqrt(np.sum(np.power(US_hat, 2), axis=0))
            #         U_hat_der = US_hat / s_hat
            #         V_hat = (R_new.T @ U_hat_der) / s_hat
            #         # V_hat = (np.linalg.inv(np.diag(s_hat)) @ (U.T @ R_new)).T
            #         # potential fix for sign issues
            #         U_hat = (R_new @ V_hat) / s_hat
            #         # U_hat_, s_hat_, V_hat_ = gsvd.gsvd(R_new)
            #     else:
            #         raise exceptions.NotImplementedError(
            #             f"Specified rotation method ({rotate_method}) "
            #             "has not been implemented."
            #         )

            # insert left singular vector into tracking np_array
            # print(f"dst: {right_sv_sampled[i].shape}; src: {V_hat.shape}")
            left_sv_sampled[i] = U_hat
            right_sv_sampled[i] = V_hat
            # right_sum += V_hat
            # right_squares += np.power(V_hat, 2)

        # compute confidence intervals of U sampled
        conf_int = resample.confidence_interval(left_sv_sampled)
        # compute standard error of left singular vector
        std_errs = scipy.stats.sem(right_sv_sampled, axis=0)
        # compute bootstrap ratios
        boot_ratios = np.divide(std_errs, V)
        return (conf_int, std_errs, boot_ratios)

    def __repr__(self):
        stg = ""
        stg += "Permutation Test Results\n"
        stg += "------------------------\n\n"
        stg += f"Ratio: {self.permute_ratio}\n\n"
        stg += "Bootstrap Test Results\n"
        stg += "----------------------\n\n"
        stg += f"Element-wise Confidence Interval: {self.dist}\n"
        stg += "\nLower CI: \n"
        stg += str(self.conf_ints[0])
        stg += "\n\nUpper CI: \n"
        stg += str(self.conf_ints[1])
        stg += "\n\nStandard Errors:\n"
        stg += str(self.std_errs)
        stg += "\n\nBootstrap Ratios:\n"
        stg += str(self.boot_ratios)
        return stg

    def __str__(self):
        stg = ""
        stg += "Permutation Test Results\n"
        stg += "------------------------\n\n"
        stg += f"Ratio: {self.permute_ratio}\n\n"
        stg += "Bootstrap Test Results\n"
        stg += "----------------------\n\n"
        stg += f"Element-wise Confidence Interval: {self.dist}\n"
        stg += "\nLower CI: \n"
        stg += str(self.conf_ints[0])
        stg += "\n\nUpper CI: \n"
        stg += str(self.conf_ints[1])
        stg += "\n\nStandard Errors:\n"
        stg += str(self.std_errs)
        stg += "\n\nBootstrap Ratios:\n"
        stg += str(self.boot_ratios)
        return stg