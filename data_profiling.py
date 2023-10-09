import pandas as pd
import numpy as np


def _load_data_from_file(filename):
    """Attempts to load the data from file using the extension provided (or by itself)"""
    if ".csv" in filename:
        _df = pd.read_csv(filename)
    elif (".xlsx" in filename) or (".xls" in filename):
        _df = pd.read_excel(filename)
    elif ".tsv" in filename:
        _df = pd.read_table(filename, delimiter="\t")
    elif ".txt" in filename:
        try:
            _df = pd.read_table(filename, delimiter="\t")
        except:
            _df = pd.read_table(filename, delimiter=",")
        finally:
            raise RuntimeError("Could not detect correct delimiter for .txt file")
    else:
        try:
            _df = pd.read_csv(filename + ".csv")
        except:
            _df = pd.read_excel(filename + ".xlsx")
        finally:
            raise ValueError(
                "File name must include file type extension (eg .xlsx/.csv)"
            )
    return _df


def _currency_cleaner(_df, fieldname: str):
    attempted_clean = (
        _df[fieldname]
        .str.replace("$", "", regex=False)
        .str.replace("€", "", regex=False)
        .str.replace("£", "", regex=False)
        .str.replace("USD", "", regex=False)
        .str.replace("GBP", "", regex=False)
        .str.replace("EUR", "", regex=False)
        .str.replace("¥", "", regex=False)
        .str.replace("₣", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.replace(",", "", regex=False)
    )
    return attempted_clean


def _detect_col_dtypes(_df):
    """Return dictionary of fieldname: datatype for each column in a dataframe"""
    col_dtypes = dict()
    for col in _df:
        # Integers
        try:
            if (
                _df[col].astype("float").astype("int").sum()
                == _df[col].astype("float").sum()
            ):
                col_dtypes[col] = "integer"
                continue
        except:
            col_dtypes[col] = None

        # Floats
        try:
            if _df[col].astype("float").sum() > 0:
                col_dtypes[col] = "float"
                continue
        except:
            col_dtypes[col] = None

        # Currencies
        attempted_clean = _currency_cleaner(_df, fieldname=col)
        try:
            pd.to_numeric(attempted_clean)
            col_dtypes[col] = "currency"
            continue
        except:
            col_dtypes[col] = None

        # Strings
        try:
            _df[col].astype("string")
            col_dtypes[col] = "string"
            continue
        except:
            col_dtypes[col] = None
    return col_dtypes


def _generate_frequency_bins(_df, fieldname: str, normalize: bool = True):
    """Converts array of numbers into labelled frequency bins

    Args:
        _df (pandas dataframe)
        colname (string): field containing the array of values.
        normalize (boolean): whether to return percentages or the counts in each bucket (Default: True)

    requires numpy and pandas
    """
    if normalize:
        col_prefix = "pct"
    else:
        col_prefix = "count"
    label_var, value_var = f"bins|{fieldname}", f"{col_prefix}|{fieldname}"

    # Save nulls for later (they aren't part of the initial bins)
    count_nulls = _df[fieldname].isna().sum()
    data = _df[fieldname].dropna()

    nbins = 10
    bins = np.histogram(data, bins=nbins)  # <-- auto-generate bins
    freqs, edges = bins

    labelled_bins = {
        f"{edges[idx] : ,.0f} to <{edges[idx + 1] : ,.0f}": count
        for idx, count in enumerate(freqs)
    }

    bin_df = pd.concat(
        [
            # Re-insert the null count at the top of the table
            pd.DataFrame([[None, count_nulls]], columns=[label_var, value_var])
            # Add the binned data next
            ,
            (
                pd.DataFrame(labelled_bins.values(), index=labelled_bins.keys())
                .reset_index()
                .rename(columns={"index": label_var, 0: value_var})
            ),
        ]
    )

    if normalize:
        bin_df.loc[:, value_var] = bin_df[value_var].transform(lambda x: x / x.sum())

    return bin_df


def _count_distinct_excel(_df, sort_by: str = "index", normalize: bool = True):
    """
    Performs Values Counts on each column of a dataframe, for data profiling purposes.

    Args:
        _df (pandas dataframe)
        sort_by (string): How to sort the outputs. Accepted strings ['value','index'] Default='index' (alphabetical)
        normalize (boolean): True for %s, False for num/counts. (Defaults to True).
    """
    if normalize:
        field_prefix = "pct|"
    else:
        field_prefix = "count|"

    _output_subtables = dict()

    col_types = _detect_col_dtypes(_df)

    for col in _df:
        # For Currency fields, clean first, then use frequency biiinin
        if col_types[col] == "currency":
            _df.loc[:, col] = pd.to_numeric(_currency_cleaner(_df, col))

        # Use value_counts() for Dimension and Low cardinality fields
        if col_types[col] == "string" or len(_df[col].value_counts().index) < 10:
            _output_subtables[col] = (
                _df[col]
                .value_counts(dropna=False, normalize=normalize)
                .reset_index()
                # .rename(columns={col: field_prefix + col, "index": col})
            )
            # rename (can't be done inline as value_counts results vary by python version)
            _output_subtables[col].columns = [col, field_prefix + col]

            # Sort order
            if sort_by.lower() == "index":
                _output_subtables[col] = _output_subtables[col].sort_values(
                    by=col, ascending=True
                )
            else:
                _output_subtables[col] = _output_subtables[col].sort_values(
                    by=field_prefix + col, ascending=False
                )

        # For Numeric fields, (incl. currency) use frequency binning to summarise data
        else:
            _output_subtables[col] = _generate_frequency_bins(
                _df, fieldname=col, normalize=normalize
            )
    return _output_subtables


def run_field_profiling(
    input_file: str, sort_by: str = "index", normalize: bool = True
):
    """
    Performs Values Counts on each column of a dataframe, for data profiling purposes.

    Outputs to Excel

    Args:
        input_file (string): filename containing data table
        sort_by (string): How to sort the outputs. Accepted strings ['value','index'] Default='index' (alphabetical)
        normalize (boolean): True for %s, False for num/counts. (Defaults to True).
    """

    # Attempt to load the data from file
    _table = _load_data_from_file(input_file)

    # Count / % Pct distinct values
    output_subtables = _count_distinct_excel(
        _table, sort_by=sort_by, normalize=normalize
    )

    output_file = (
        input_file.replace(".csv", "")
        .replace(".xls", "")
        .replace(".xlsx", "")
        .replace(".tsv", "")
        .replace("txt", "")
        + ".xlsx"
    )
    output_file = f"profiled_{output_file}"

    with pd.ExcelWriter(output_file) as writer:
        for idx, subt in enumerate(output_subtables):
            num_spacer_columns = 1

            # Save to Excel (subtables next to each other in worksheet)
            output_subtables[subt].to_excel(
                writer,
                sheet_name="column_profiling",
                startcol=idx * (2 + num_spacer_columns),
                index=False,
            )
    print(f"file saved:{output_file}")
    return
